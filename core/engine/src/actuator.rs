use async_trait::async_trait;

#[derive(Debug)]
pub enum ActuatorMovingError {
    CommandAborted,
    CommunicationError,
}

#[derive(Debug)]
#[allow(dead_code)]
pub enum ActuatorAbortingError {
    CommunicationError,
}

#[async_trait]
pub trait Actuator: Send + Sync {
    async fn move_to(&self, degree: u16) -> Result<(), ActuatorMovingError>;
    async fn abort(&self) -> Result<(), ActuatorAbortingError>;
}
