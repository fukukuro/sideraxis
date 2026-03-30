use crate::actuator::{Actuator, ActuatorMovingError};
use std::sync::Arc;
use tokio::sync::{mpsc, oneshot};

#[derive(PartialEq, Clone, Copy, Debug)]
pub enum StopRailState {
    GO,
    STOP,
}

struct StopRailCommand {
    state: StopRailState,
    responder: oneshot::Sender<Result<(), ActuatorMovingError>>,
}

pub struct StopRail {
    cmd_tx: mpsc::Sender<StopRailCommand>,
}

impl StopRail {
    pub fn new(go_deg: u16, stop_deg: u16, actuator: Arc<dyn Actuator>) -> Self {
        let (cmd_tx, mut cmd_rx) = mpsc::channel::<StopRailCommand>(10);
        tokio::spawn(async move {
            let mut _current_state: Option<StopRailState> = None;
            let mut _active_responder: Option<oneshot::Sender<Result<(), ActuatorMovingError>>> =
                None;

            let mut pending_cmd: Option<StopRailCommand> = None;

            loop {
                let cmd = if let Some(c) = pending_cmd.take() {
                    c
                } else {
                    match cmd_rx.recv().await {
                        Some(c) => c,
                        None => break,
                    }
                };

                let target = cmd.state;
                _active_responder = Some(cmd.responder);
                let deg = if target == StopRailState::GO {
                    go_deg
                } else {
                    stop_deg
                };

                tokio::select! {
                    result = actuator.move_to(deg) => {
                        if let Some(res) = _active_responder.take() {
                            let _ = res.send(result);
                        }
                        _current_state = Some(target);
                    }
                    next_msg = cmd_rx.recv() => {
                        if let Some(next_cmd) = next_msg {
                            if let Some(res) = _active_responder.take() {
                                let _ = res.send(Err(ActuatorMovingError::CommandAborted));
                            }
                            let _ = actuator.abort().await;
                            pending_cmd = Some(next_cmd);
                            continue;
                        }
                    }
                }
            }
        });

        Self { cmd_tx }
    }

    pub async fn move_to(&self, state: StopRailState) -> Result<(), ActuatorMovingError> {
        let (tx, rx) = oneshot::channel();
        let cmd = StopRailCommand {
            state,
            responder: tx,
        };

        self.cmd_tx
            .send(cmd)
            .await
            .map_err(|_| ActuatorMovingError::CommunicationError)?;

        rx.await.map_err(|_| ActuatorMovingError::CommandAborted)?
    }
}
