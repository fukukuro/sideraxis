use crate::actuator::{Actuator, ActuatorAbortingError, ActuatorMovingError};
use async_trait::async_trait;
use std::sync::{Arc, Mutex};
use std::time::Duration;
use tokio::time::sleep;

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
            if start_deg < target {
                *curr += 1;
            } else {
                *curr -= 1;
            }
            if *curr % 15 == 0 {
                println!("[{}] {}°", self.name, *curr);
            }
        }
        Ok(())
    }
    async fn abort(&self) -> Result<(), ActuatorAbortingError> {
        Ok(())
    }
}
