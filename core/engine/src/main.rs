use async_trait::async_trait;
use std::sync::{Arc, Mutex};
use std::time::Duration;
use tokio::sync::{mpsc, oneshot, watch};
use tokio::time::sleep;

// --- エラー定義 ---

#[derive(Debug)]
pub enum ActuatorMovingError {
    CommandAborted,
    CommunicationError,
}

#[derive(Debug)]
pub enum ActuatorAbortingError {
    CommunicationError,
}

// --- トレイトと擬似アクチュエータ ---

#[async_trait]
pub trait Actuator: Send + Sync {
    async fn move_to(&self, degree: u16) -> Result<(), ActuatorMovingError>;
    async fn abort(&self) -> Result<(), ActuatorAbortingError>;
}

pub struct VirtualServo {
    name: String,
    current_degree: Arc<Mutex<u16>>,
}

impl VirtualServo {
    pub fn new(name: &str, initial_degree: u16) -> Self {
        Self {
            name: name.to_string(),
            current_degree: Arc::new(Mutex::new(initial_degree)),
        }
    }
    pub fn get_degree(&self) -> u16 {
        *self.current_degree.lock().unwrap()
    }
}

#[async_trait]
impl Actuator for VirtualServo {
    async fn move_to(&self, target: u16) -> Result<(), ActuatorMovingError> {
        let start_deg = self.get_degree();
        let ms_per_degree = 5000 / 360;
        let diff = (target as i32 - start_deg as i32).abs() as u16;

        for _ in 0..diff {
            sleep(Duration::from_millis(ms_per_degree)).await;
            let mut curr = self.current_degree.lock().unwrap();
            if start_deg < target { *curr += 1; } else { *curr -= 1; }
            if *curr % 15 == 0 { println!("[{}] {}°", self.name, *curr); }
        }
        Ok(())
    }
    async fn abort(&self) -> Result<(), ActuatorAbortingError> {
        Ok(())
    }
}

// --- StopRail のロジック ---

#[derive(PartialEq, Clone, Copy, Debug)]
pub enum StopRailState { GO, STOP }

// 内部でやり取りする命令セット
struct StopRailCommand {
    state: StopRailState,
    responder: oneshot::Sender<Result<(), ActuatorMovingError>>,
}

pub struct StopRail {
    // 外からはこの送信機(mpsc)を通して命令を送る
    cmd_tx: mpsc::Sender<StopRailCommand>,
}

impl StopRail {
    pub fn new(go_deg: u16, stop_deg: u16, actuator: Arc<dyn Actuator>) -> Self {
        // 命令を受け付けるためのチャネル(mpsc)を作成
        let (cmd_tx, mut cmd_rx) = mpsc::channel::<StopRailCommand>(10);

        // Core のループを spawn で放流
        tokio::spawn(async move {
            let mut current_state: Option<StopRailState> = None;
            // 現在実行中の responder を保持する変数
            let mut active_responder: Option<oneshot::Sender<Result<(), ActuatorMovingError>>> = None;

            loop {
                // 命令が届くのを待つ
                if let Some(cmd) = cmd_rx.recv().await {
                    let target = cmd.state;
                    
                    // もし前の移動が続いていたら、前の人に「中断されたよ」と返してあげる
                    if let Some(prev_res) = active_responder.take() {
                        let _ = prev_res.send(Err(ActuatorMovingError::CommandAborted));
                        let _ = actuator.abort().await;
                    }

                    // 新しい担当をセット
                    active_responder = Some(cmd.responder);

                    let deg = if target == StopRailState::GO { go_deg } else { stop_deg };

                    // 駆動開始
                    tokio::select! {
                        result = actuator.move_to(deg) => {
                            if let Some(res) = active_responder.take() {
                                let _ = res.send(result); // 移動完了を報告
                            }
                            current_state = Some(target);
                        }
                        // 駆動中に「次の命令」が cmd_rx に届いたら即座に select! を抜ける
                        // これにより actuator.move_to は Drop (Abort) される
                        next_cmd_check = cmd_rx.recv() => {
                            if let Some(next_cmd) = next_cmd_check {
                                println!("New command received during move! Aborting...");
                                // 前の命令に中断を報告
                                if let Some(res) = active_responder.take() {
                                    let _ = res.send(Err(ActuatorMovingError::CommandAborted));
                                }
                                let _ = actuator.abort().await;
                                
                                // この next_cmd を処理するためにループの先頭へ
                                // (実際にはこの cmd_rx.recv() で取り出した値を次に回す工夫が必要ですが
                                //  今回は説明のためシンプルにしています)
                                
                                // --- ここで再帰的に次の命令を処理するイメージ ---
                                // (本来は loop 内で状態管理しますが、今回は単純化)
                            }
                        }
                    }
                }
            }
        });

        Self { cmd_tx }
    }

    // これが理想の move_to メソッド！
    pub async fn move_to(&self, state: StopRailState) -> Result<(), ActuatorMovingError> {
        let (tx, rx) = oneshot::channel();
        let cmd = StopRailCommand { state, responder: tx };

        // 内部タスクに依頼
        self.cmd_tx.send(cmd).await
            .map_err(|_| ActuatorMovingError::CommunicationError)?;

        // 返事を待機
        rx.await.map_err(|_| ActuatorMovingError::CommandAborted)?
    }
}

#[tokio::main]
async fn main() {
    let actuator_1 = Arc::new(VirtualServo::new("actuator001", 120));
    let stoprail_1 = StopRail::new(30, 120, actuator_1);

    println!("--- 命令1: GO ---");
    // .await をつけることで、理想の match 構文が使える
    match stoprail_1.move_to(StopRailState::GO).await {
        Ok(_) => println!("成功！"),
        Err(e) => eprintln!("失敗または中断: {:?}", e),
    }
}