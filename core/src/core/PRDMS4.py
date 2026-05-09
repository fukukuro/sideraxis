import asyncio
from typing import Tuple, Optional
from infrastructure.v_clock import VClock
from infrastructure.task_delegator import TaskDelegator
from hal.worker import SerialWorker
from hal.gateway import SerialGateway
from hal.component import Sensor, Actuator, ManualActuator
from core.place import Place
from core.stop_rail import StopRail
from core.two_way_point import TwoWayPoint
from core.train import Train, TrainActions
from core.flag_manager import FlagManager
from infrastructure.logger import logger


class PRDMS4:
    def __init__(self, v_clock: VClock):
        self._v_clock = v_clock
        self._task_delegator = TaskDelegator()
        self._flag_manager = FlagManager()
        self._serial_workers: list[SerialWorker] = []
        self._serial_gateways: list[SerialGateway] = []
        self._generic_servos: list[Actuator] = []
        self._places: list[Place] = []
        self._stop_rails: list[StopRail] = []
        self._two_way_points: list[TwoWayPoint] = []
        self._generic_sensors: list[Sensor] = []
        self._sensor_metadata: list[dict] = []
        self._stop_rail_metadata: list[dict] = []
        self._two_way_point_metadata: list[dict] = []
        self._trains: list[Train] = []

    # --- Registration Methods ---

    def register_worker(self, worker: SerialWorker) -> int:
        self._serial_workers.append(worker)
        return len(self._serial_workers) - 1

    def register_gateway(self, gateway: SerialGateway) -> int:
        self._serial_gateways.append(gateway)
        return len(self._serial_gateways) - 1

    def register_servo(self, servo: Actuator) -> int:
        self._generic_servos.append(servo)
        return len(self._generic_servos) - 1

    def register_place(self, place: Place) -> int:
        self._places.append(place)
        return len(self._places) - 1

    def register_stop_rail(self, stop_rail: StopRail) -> int:
        self._stop_rails.append(stop_rail)
        return len(self._stop_rails) - 1

    def create_stop_rail(
        self, 
        servo_id: int, 
        stop_position: int, 
        go_position: int, 
        place_ids: Tuple[int, int]
    ) -> int:
        """Creates and registers a StopRail by looking up its dependencies."""
        if servo_id < 0 or servo_id >= len(self._generic_servos):
            raise ValueError(f"Servo ID {servo_id} not found")
        
        for p_id in place_ids:
            if p_id < 0 or p_id >= len(self._places):
                raise ValueError(f"Place ID {p_id} not found")

        servo = self._generic_servos[servo_id]
        places = (self._places[place_ids[0]], self._places[place_ids[1]])
        
        stop_rail = StopRail(servo, stop_position, go_position, places)
        idx = self.register_stop_rail(stop_rail)
        self._stop_rail_metadata.append({
            "servo_id": servo_id,
            "stop_position": stop_position,
            "go_position": go_position,
            "place_ids": place_ids
        })
        return idx

    def register_two_way_point(self, point: TwoWayPoint) -> int:
        self._two_way_points.append(point)
        return len(self._two_way_points) - 1

    def create_two_way_point(
        self,
        servo_id: int,
        normal_position: int,
        reverse_position: int,
        place_ids: Tuple[int, int, int]
    ) -> int:
        """Creates and registers a TwoWayPoint by looking up its dependencies."""
        if servo_id < 0 or servo_id >= len(self._generic_servos):
            raise ValueError(f"Servo ID {servo_id} not found")
        
        for p_id in place_ids:
            if p_id < 0 or p_id >= len(self._places):
                raise ValueError(f"Place ID {p_id} not found")

        servo = self._generic_servos[servo_id]
        places = (self._places[place_ids[0]], self._places[place_ids[1]], self._places[place_ids[2]])
        
        point = TwoWayPoint(servo, normal_position, reverse_position, places)
        idx = self.register_two_way_point(point)
        self._two_way_point_metadata.append({
            "servo_id": servo_id,
            "normal_position": normal_position,
            "reverse_position": reverse_position,
            "place_ids": place_ids
        })
        return idx

    def register_sensor(self, sensor: Sensor, metadata: dict) -> int:
        self._generic_sensors.append(sensor)
        self._sensor_metadata.append(metadata)
        return len(self._generic_sensors) - 1

    def create_manual_servo(self, display_name: str) -> Actuator:
        """Creates a 'servo' that is actually operated manually by a human."""
        actuator = ManualActuator(display_name, self._task_delegator)
        servo = actuator.generic_servo
        self.register_servo(servo)
        return servo

    def create_train(
        self,
        display_name: str,
        itinerary: list[int],
        actions: Optional[list[TrainActions]] = None,
        initial_index: Tuple[int, ...] = (0,),
    ) -> Train:
        """
        運行中に新しい列車を生成し、(可能であれば)即座に処理を開始します。
        """
        train = Train(display_name)
        train.set_itinerary(itinerary, initial_index)
        if actions:
            train.stab = actions
        else:
            train.stab = []

        self._trains.append(train)


        # すでにイベントループが回っている場合は、即座にスタブ処理を開始する
        try:
            asyncio.create_task(train.process_stub(self))
        except RuntimeError:
            # ループ開始前であれば、後ほど run() で一括開始される
            pass

        return train

    async def create_sensor(self, gateway_idx: int, pin: int, associated_place_id: int) -> Sensor:
        """Creates a sensor and registers it with a place for tracking."""
        gateway = self._serial_gateways[gateway_idx]
        
        # Connect sensor trigger to PRDMS4 tracking logic
        sensor = await gateway.create_sensor(
            pin, 
            lambda count: self._on_sensor_trigger(associated_place_id, count)
        )
        self._generic_sensors.append(sensor)
        self._sensor_metadata.append({
            "gateway_id": gateway_idx,
            "pin": pin,
            "associated_place_id": associated_place_id
        })
        return sensor

    def get_system_snapshot(self) -> dict:
        """Returns a complete snapshot of the system state for API/UI."""
        return {
            "v_clock": self._v_clock.getVclockTime(),
            "flags": self._flag_manager.get_all_flags(),
            "trains": [t.get_status() for t in self._trains],
            "places": [
                {
                    "id": i,
                    "occupier": p.occupancy.occupier.display_name if p.occupancy else None
                } for i, p in enumerate(self._places)
            ],
            "gateways": [
                {
                    "id": i,
                    "display_name": g.display_name,
                    "initialized": g._initialized,
                    "i2c_initialized": g._i2c_initialized
                } for i, g in enumerate(self._serial_gateways)
            ],
            "servos": [
                {
                    "id": i,
                    "last_value": s.last_value
                } for i, s in enumerate(self._generic_servos)
            ],
            "two_way_points": [
                {"id": i, **meta} 
                for i, meta in enumerate(self._two_way_point_metadata)
            ],
            "stop_rails": [
                {"id": i, **meta} 
                for i, meta in enumerate(self._stop_rail_metadata)
            ]
        }

    # --- Lifecycle Methods ---

    def start_all_workers(self):
        """Starts all serial worker threads."""
        for worker in self._serial_workers:
            worker.start()
        logger.info(f"Started {len(self._serial_workers)} serial workers.")

    def stop_all_workers(self):
        """Stops all serial worker threads."""
        for worker in self._serial_workers:
            worker.stop()
        logger.info("Stopped all serial workers.")

    def _on_sensor_trigger(self, place_id: int, count: int):
        """Called when a sensor associated with place_id triggers."""
        # Find which train is occupying this place (for count=1)
        # or which train is EXPECTED at this place.

        # 1. Check if a train is already occupying it
        occupancy = self._places[place_id].occupancy
        if occupancy and occupancy.occupier:
            occupancy.occupier.handle_sensor_event(self, place_id, count)
            return

        # 2. If not yet occupied (shouldn't happen with proper interlocking), 
        # find a train whose next place is this one.
        for train in self._trains:
            if train._train_place_index is not None:
                last_idx = max(train._train_place_index)
                if last_idx + 1 < len(train._train_places):
                    if train._train_places[last_idx + 1] == place_id:
                        train.handle_sensor_event(self, place_id, count)
                        return

    async def run(self):
        """Starts processing for all trains and ensures workers are running."""
        self.start_all_workers()
        await asyncio.gather(*(train.process_stub(self) for train in self._trains))