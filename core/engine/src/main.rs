mod actuator;
mod stoprail;
mod virtual_servo;
use std::sync::Arc;
use stoprail::{StopRail, StopRailState};
use virtual_servo::VirtualServo;

#[tokio::main]
async fn main() {
    let actuator_1 = Arc::new(VirtualServo::new("actuator001", 120));
    let stoprail_1 = StopRail::new(30, 120, actuator_1);
    match stoprail_1.move_to(StopRailState::GO).await {
        Ok(_) => println!("成功！"),
        Err(e) => match e{
            actuator::ActuatorMovingError::CommandAborted => println!("中断"),
            actuator::ActuatorMovingError::CommunicationError => println!("通信エラー"),
        },
    }
    match stoprail_1.move_to(StopRailState::STOP).await {
        Ok(_) => println!("成功！"),
        Err(e) => eprintln!("失敗または中断: {:?}", e),
    }
    println!("アクチュエータ単体");
}
