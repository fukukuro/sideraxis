mod actuator;
mod place;
mod stoprail;
mod virtual_servo;
use std::sync::Arc;
use stoprail::{StopRail, StopRailState};
use virtual_servo::VirtualServo;
use place::{Change, Constraint, Place, PlaceManager, PlaceStatus, Transaction};


#[tokio::main]
async fn main() {
    let actuator_1 = Arc::new(VirtualServo::new("actuator001", 120));
    let stoprail_1 = StopRail::new(30, 120, actuator_1);
    match stoprail_1.move_to(StopRailState::GO).await {
        Ok(_) => println!("成功！"),
        Err(e) => match e {
            actuator::ActuatorMovingError::CommandAborted => println!("中断"),
            actuator::ActuatorMovingError::CommunicationError => println!("通信エラー"),
        },
    }
    match stoprail_1.move_to(StopRailState::STOP).await {
        Ok(_) => println!("成功！"),
        Err(e) => eprintln!("失敗または中断: {:?}", e),
    }
    println!("アクチュエータ単体");
    //以下
    // 1. 初期データ（地点と制約）の準備
    let places = vec![
        Place::new("駅ホームA"), // ID: 0
        Place::new("分岐点1"),   // ID: 1
        Place::new("本線出口"),   // ID: 2
    ];

    // 「分岐点1(1) が占有されているなら、駅ホームA(0) と 本線出口(2) は同じ列車であること」
    // という制約を仮に作ってみます
    let constraints = vec![
        Constraint::AllOf(vec![
            Constraint::SameOwner(vec![0, 1, 2]),
        ])
    ];

    // 2. マネージャーを起動し、ハンドルを受け取る
    // この一行で裏側で Runner タスクが動き出します
    let manager = PlaceManager::start(places, constraints);

    // --- 利用シーン1: 列車が進入してきたとき (Transaction) ---
    let handle_for_logic = manager.clone();
    tokio::spawn(async move {
        let tx = Transaction {
            changes: vec![
                Change { target_place_id: 0, target_status: PlaceStatus::OccupiedBy(101) },
                Change { target_place_id: 1, target_status: PlaceStatus::OccupiedBy(101) },
                Change { target_place_id: 2, target_status: PlaceStatus::OccupiedBy(101) },
            ],
        };

        match handle_for_logic.execute_transaction(tx).await {
            Ok(_) => println!("列車101: 進路構成に成功しました"),
            Err(e) => println!("列車101: 進路構成を拒否されました: {}", e),
        }
    });

    // --- 利用シーン2: Web APIなどで現在の状態を覗き見るとき (GetStatus) ---
    let handle_for_api = manager.clone();
    tokio::spawn(async move {
        // 1秒待ってから状態を確認してみる
        tokio::time::sleep(std::time::Duration::from_secs(1)).await;
        
        match handle_for_api.get_status().await {
            Ok(statuses) => {
                println!("--- 現在の運行状況 ---");
                for (id, status) in statuses.iter().enumerate() {
                    println!("地点ID {}: {:?}", id, status);
                }
            }
            Err(e) => println!("APIエラー: {}", e),
        }
    });

    tokio::time::sleep(std::time::Duration::from_millis(500)).await;
    let illegal_tx = Transaction {
        changes: vec![
            Change { target_place_id: 1, target_status: PlaceStatus::OccupiedBy(999) },
        ],
    };

    match manager.execute_transaction(illegal_tx).await {
        Ok(_) => println!("不正な操作が通ってしまいました"),
        Err(e) => println!("不正な操作をブロックしました: {}", e),
    }

    // サンプル実行のために少し待機
    tokio::time::sleep(std::time::Duration::from_secs(2)).await;
}
