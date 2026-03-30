use tokio::sync::{mpsc, oneshot, watch};

// --- 基本型定義 ---

type TrainId = u16;
type PlaceId = u16;

#[derive(Clone, Debug, PartialEq)]
pub enum PlaceStatus {
    Empty,
    OccupiedBy(TrainId),
}

#[derive(Clone, Debug)]
pub struct Place {
    pub name: String,
    status_tx: watch::Sender<PlaceStatus>,
    status_rx: watch::Receiver<PlaceStatus>,
}

impl Place {
    pub fn new(name: &str) -> Self {
        let (tx, rx) = watch::channel(PlaceStatus::Empty);
        Self {
            name: name.to_string(),
            status_tx: tx,
            status_rx: rx,
        }
    }

    pub fn subscribe(&self) -> watch::Receiver<PlaceStatus> {
        self.status_rx.clone()
    }

    pub fn set_status(&self, status: PlaceStatus) -> Result<(), String> {
        self.status_tx
            .send(status)
            .map_err(|_| "Receiver dropped".to_string())?;
        Ok(())
    }
}

// --- トランザクション・制約 ---

#[derive(Clone, Debug)]
pub enum Constraint {
    AllNone(Vec<PlaceId>),
    SameOwner(Vec<PlaceId>),
    AnyOf(Vec<Constraint>),
    AllOf(Vec<Constraint>),
}

#[derive(Debug)]
pub struct Transaction {
    pub changes: Vec<Change>,
}

#[derive(Clone, Debug)]
pub struct Change {
    pub target_place_id: PlaceId,
    pub target_status: PlaceStatus,
}

// --- マネージャー本体（Runner） ---

/// 外部からは隠蔽される、実体としてのマネージャー
pub struct PlaceManager {
    core: PlaceManagerCore,
    receiver: mpsc::Receiver<ManagerCommand>,
}

struct PlaceManagerCore {
    places: Vec<Place>,
    constraints: Vec<Constraint>,
}

impl PlaceManager {
    /// マネージャーを生成し、即座にバックグラウンドタスクとして起動する。
    /// 操作用の Handle のみを返す。
    pub fn start(places: Vec<Place>, constraints: Vec<Constraint>) -> PlaceManagerHandle {
        let (tx, rx) = mpsc::channel(32);
        let core = PlaceManagerCore { places, constraints };
        let manager = Self {
            core,
            receiver: rx,
        };

        // 所有権を async ブロックの中に move し、タスクを起動
        tokio::spawn(async move {
            manager.run().await;
        });

        PlaceManagerHandle::new(tx)
    }

    /// メインループ（private）
    async fn run(mut self) {
        tracing::info!("PlaceManager runner started.");
        while let Some(command) = self.receiver.recv().await {
            match command {
                ManagerCommand::ExecuteTransaction { transaction, responder } => {
                    let result = self.core.transaction(transaction);
                    let _ = responder.send(result);
                }
                ManagerCommand::GetStatus { responder } => {
                    let status = self.core.places
                        .iter()
                        .map(|p| p.subscribe().borrow().clone())
                        .collect();
                    let _ = responder.send(status);
                }
            }
        }
    }
}

impl PlaceManagerCore {
    fn transaction(&self, transaction: Transaction) -> Result<(), String> {
        // 1. スナップショット作成
        let mut snapshot: Vec<PlaceStatus> = self.places
            .iter()
            .map(|p| p.subscribe().borrow().clone())
            .collect();

        // 2. 仮適用
        for change in &transaction.changes {
            let idx = change.target_place_id as usize;
            let status = snapshot.get_mut(idx)
                .ok_or_else(|| format!("Place ID {} is out of bounds", idx))?;
            *status = change.target_status.clone();
        }

        // 3. 検証
        for (i, constraint) in self.constraints.iter().enumerate() {
            if !self.evaluate_constraint(constraint, &snapshot) {
                return Err(format!("Constraint violation at index {}", i));
            }
        }

        // 4. 本反映
        for change in transaction.changes {
            let idx = change.target_place_id as usize;
            self.places[idx].set_status(change.target_status)?;
        }
        
        Ok(())
    }

    fn evaluate_constraint(&self, constraint: &Constraint, snapshot: &[PlaceStatus]) -> bool {
        match constraint {
            Constraint::AllNone(ids) => ids.iter().all(|&id| {
                matches!(snapshot.get(id as usize), Some(PlaceStatus::Empty))
            }),
            Constraint::SameOwner(ids) => {
                if ids.is_empty() { return true; }
                if let Some(PlaceStatus::OccupiedBy(first_tid)) = snapshot.get(ids[0] as usize) {
                    ids.iter().all(|&id| {
                        if let Some(PlaceStatus::OccupiedBy(tid)) = snapshot.get(id as usize) {
                            tid == first_tid
                        } else {
                            false
                        }
                    })
                } else {
                    false
                }
            }
            Constraint::AnyOf(rules) => rules.iter().any(|r| self.evaluate_constraint(r, snapshot)),
            Constraint::AllOf(rules) => rules.iter().all(|r| self.evaluate_constraint(r, snapshot)),
        }
    }
}

// --- 操作窓口（Handle） ---

pub enum ManagerCommand {
    ExecuteTransaction {
        transaction: Transaction,
        responder: oneshot::Sender<Result<(), String>>,
    },
    GetStatus {
        responder: oneshot::Sender<Vec<PlaceStatus>>,
    },
}

#[derive(Clone)]
pub struct PlaceManagerHandle {
    tx: mpsc::Sender<ManagerCommand>,
}

impl PlaceManagerHandle {
    fn new(tx: mpsc::Sender<ManagerCommand>) -> Self {
        Self { tx }
    }

    pub async fn execute_transaction(&self, transaction: Transaction) -> Result<(), String> {
        let (resp_tx, resp_rx) = oneshot::channel();
        self.tx.send(ManagerCommand::ExecuteTransaction {
            transaction,
            responder: resp_tx,
        }).await.map_err(|_| "Manager task dropped".to_string())?;
        resp_rx.await.map_err(|_| "Oneshot closed".to_string())?
    }

    pub async fn get_status(&self) -> Result<Vec<PlaceStatus>, String> {
        let (resp_tx, resp_rx) = oneshot::channel();
        self.tx.send(ManagerCommand::GetStatus {
            responder: resp_tx,
        }).await.map_err(|_| "Manager task dropped".to_string())?;
        resp_rx.await.map_err(|_| "Oneshot closed".to_string())
    }
}