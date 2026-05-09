from fastapi import APIRouter, HTTPException
from core.PRDMS4 import PRDMS4
from hal.worker import SerialWorker
from hal.gateway import SerialGateway
from pydantic import BaseModel

class SerialWorkerCreationArgs(BaseModel):
    port:str
    baud:int
    display_name:str

class GatewayCreationArgs(BaseModel):
    worker_id: int
    display_name: str

class ServoCreationArgs(BaseModel):
    gateway_id: int
    address: int
    pin: int
    display_name: str = "PCA9685 Servo"

class SensorCreationArgs(BaseModel):
    gateway_id: int
    pin: int
    associated_place_id: int

class I2CInitializationArgs(BaseModel):
    sda: int
    scl: int

class SerialWorkerRouter:
    def __init__(self, PRDMS4:PRDMS4):
        self.PRDMS4 = PRDMS4
    def get_router(self):
        serial_worker_router = APIRouter(prefix="/workers", tags=["workers"])
        r = serial_worker_router
        @r.get("/")
        async def workers():
            serial_workers = self.PRDMS4._serial_workers
            workers_list = []
            for idx,worker in enumerate(serial_workers):
                workers_list.append({
                    "id":idx,
                    "display_name":worker.display_name,
                    "port":worker.port,
                    "baud":worker.baud,
                    "running":worker.running
                })
            return workers_list
        @r.post("/")
        async def create_worker(params:SerialWorkerCreationArgs):
            self.PRDMS4.register_worker(SerialWorker(params.port,params.baud,params.display_name))
            return

        @r.post("/{id}/start")
        async def start_worker(id: int):
            if id < 0 or id >= len(self.PRDMS4._serial_workers):
                raise HTTPException(status_code=404, detail="Worker not found")
            self.PRDMS4._serial_workers[id].start()
            return {"status": "success"}

        @r.post("/{id}/stop")
        async def stop_worker(id: int):
            if id < 0 or id >= len(self.PRDMS4._serial_workers):
                raise HTTPException(status_code=404, detail="Worker not found")
            self.PRDMS4._serial_workers[id].stop()
            return {"status": "success"}
        
        return serial_worker_router

class GatewayRouter:
    def __init__(self, PRDMS4:PRDMS4):
        self.PRDMS4 = PRDMS4
    def get_router(self):
        gateway_router = APIRouter(prefix="/gateway", tags=["gateway"])
        r = gateway_router
        @r.get("/")
        async def gateways():
            gateways_list = []
            for idx, gateway in enumerate(self.PRDMS4._serial_gateways):
                gateways_list.append({
                    "id": idx,
                    "display_name": gateway.display_name,
                    "initialized": gateway._initialized,
                    "i2c_initialized": gateway._i2c_initialized,
                    "sda_pin": gateway._sda_pin,
                    "scl_pin": gateway._scl_pin
                })
            return gateways_list

        @r.post("/")
        async def create_gateway(params: GatewayCreationArgs):
            if params.worker_id < 0 or params.worker_id >= len(self.PRDMS4._serial_workers):
                raise HTTPException(status_code=404, detail="Worker not found")
            worker = self.PRDMS4._serial_workers[params.worker_id]
            self.PRDMS4.register_gateway(SerialGateway(worker, params.display_name))
            return {"status": "success"}

        @r.post("/{id}/i2c")
        async def init_i2c(id: int, params: I2CInitializationArgs):
            if id < 0 or id >= len(self.PRDMS4._serial_gateways):
                raise HTTPException(status_code=404, detail="Gateway not found")
            gateway = self.PRDMS4._serial_gateways[id]
            await gateway.initialize_i2c(params.sda, params.scl)
            return {"status": "success"}

        return gateway_router

class ServoRouter:
    def __init__(self, PRDMS4:PRDMS4):
        self.PRDMS4 = PRDMS4
    def get_router(self):
        servo_router = APIRouter(prefix="/servo", tags=["servo"])
        r = servo_router
        @r.get("/")
        def servos():
            servos_list = []
            for idx, servo in enumerate(self.PRDMS4._generic_servos):
                servos_list.append({
                    "id": idx,
                    "display_name": servo.display_name,
                    "last_value": servo.last_value
                })
            return servos_list

        @r.post("/")
        async def create_servo(params: ServoCreationArgs):
            if params.gateway_id < 0 or params.gateway_id >= len(self.PRDMS4._serial_gateways):
                raise HTTPException(status_code=404, detail="Gateway not found")
            gateway = self.PRDMS4._serial_gateways[params.gateway_id]
            servo = await gateway.create_PCA9685_servo(params.address, params.pin)
            servo.display_name = params.display_name # ここで名前をセット
            idx = self.PRDMS4.register_servo(servo)
            return {"status": "success", "servo_id": idx}

        @r.post("/{id}/move")
        async def move_servo(id: int, value: int):
            if id < 0 or id >= len(self.PRDMS4._generic_servos):
                raise HTTPException(status_code=404, detail="Servo not found")
            await self.PRDMS4._generic_servos[id].move(value)
            return {"status": "success"}

        @r.post("/manual")
        async def create_manual_servo(display_name: str):
            idx = self.PRDMS4.create_manual_servo(display_name)
            # Since create_manual_servo already registers it and returns the GenericServo, 
            # we just need to find its index.
            # (Note: create_manual_servo was modified to register internally)
            return {"status": "success", "servo_id": len(self.PRDMS4._generic_servos) - 1}

        return servo_router

class SensorRouter:
    def __init__(self, PRDMS4:PRDMS4):
        self.PRDMS4 = PRDMS4
    def get_router(self):
        sensor_router = APIRouter(prefix="/sensor", tags=["sensor"])
        r = sensor_router
        
        @r.get("/")
        async def get_sensors():
            return self.PRDMS4._sensor_metadata

        @r.post("/")
        async def create_sensor(params: SensorCreationArgs):
            if params.gateway_id < 0 or params.gateway_id >= len(self.PRDMS4._serial_gateways):
                raise HTTPException(status_code=404, detail="Gateway not found")
            
            # Use PRDMS4.create_sensor to setup logic and tracking
            await self.PRDMS4.create_sensor(
                gateway_idx=params.gateway_id,
                pin=params.pin,
                associated_place_id=params.associated_place_id
            )
            return {"status": "success"}

        return sensor_router

class HalRouter:
    def __init__(self, PRDMS4:PRDMS4):
        self.PRDMS4 = PRDMS4
    def get_router(self):
        hal_router = APIRouter(prefix="/hal", tags=["hal"])
        hal_router.include_router(SerialWorkerRouter(self.PRDMS4).get_router())
        hal_router.include_router(GatewayRouter(self.PRDMS4).get_router())
        hal_router.include_router(ServoRouter(self.PRDMS4).get_router())
        hal_router.include_router(SensorRouter(self.PRDMS4).get_router())
        return hal_router
