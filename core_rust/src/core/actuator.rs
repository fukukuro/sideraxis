//"角度"への転換命令を指令できるもの(サーボなど)
pub trait MoveToDeg {
    fn move_to(&mut self, deg: u16);
    fn current_deg(&self) -> u16;
}

//"状態"が反映されるべきもの(サーボ,液晶など)
pub trait Actuator {
    fn should_reflect(&self) -> bool;
    fn clear_reflection_flag(&mut self);
}
//サーボの実体
pub enum ServoDevice {
    InIntegratedDevice { integrated_device_id: u16 },
}
//MoveToDegできるもののEnum
pub enum OrientActuator {
    Servo(Servo),
}

impl Actuator for OrientActuator {
    fn should_reflect(&self) -> bool {
        match self {
            OrientActuator::Servo(servo) => servo.should_reflect(), // サーボのメソッドを呼ぶ
        }
    }

    fn clear_reflection_flag(&mut self) {
        match self {
            OrientActuator::Servo(servo) => servo.clear_reflection_flag(),
        }
    }
}

impl MoveToDeg for OrientActuator {
    fn move_to(&mut self, deg: u16) {
        match self {
            OrientActuator::Servo(servo) => servo.move_to(deg),
        }
    }

    fn current_deg(&self) -> u16 {
        match self {
            OrientActuator::Servo(servo) => servo.current_deg(),
        }
    }
}

// サーボ
pub struct Servo {
    current_deg: u16,
    should_reflect: bool,
    servo_device: ServoDevice,
}

impl Servo {
    pub fn new(init_deg: u16, servo_device: ServoDevice) -> Self {
        Self {
            current_deg: init_deg % 360, // 💡 初期値が0固定だったバグをここで修正
            should_reflect: true,
            servo_device,
        }
    }
}

impl MoveToDeg for Servo {
    fn move_to(&mut self, deg: u16) {
        let target_deg = if deg >= 360 { deg % 360 } else { deg };
        //差分ありの場合は角度更新andフラグ立て
        if self.current_deg != target_deg {
            self.current_deg = target_deg;
            self.should_reflect = true;
        }
    }
    
    fn current_deg(&self) -> u16 {
        self.current_deg
    }
}

impl Actuator for Servo {
    fn should_reflect(&self) -> bool {
        self.should_reflect
    }
    fn clear_reflection_flag(&mut self) {
        self.should_reflect = false;
    }
}

struct ActuatorManager {
    actuators: Vec<OrientActuator>,
}

impl ActuatorManager {
    pub fn new() -> Self {
        Self {
            actuators: Vec::new(),
        }
    }
    //Reactのレンダリング的な
    pub fn reflect(&mut self) {
        for (i, actuator) in self.actuators.iter_mut().enumerate() {
            if actuator.should_reflect() {
                // あとで実装
                actuator.clear_reflection_flag();//フラグクリア
            }
        }
    }
}