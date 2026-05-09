from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, List, Dict


from infrastructure.logger import logger
from hal.worker import SerialWorker
from hal.component import Actuator, Sensor
import exceptions


class SerialGateway:
    """
    シリアルワーカーとの通信の,バリデーションなどを担当するクラス.
    """

    def __init__(self, worker: SerialWorker, display_name: str = ""):
        self._worker: SerialWorker = worker
        self.display_name: str = display_name
        self._initialized: bool = False
        self._worker.register_noqid_callback(self._handle_no_qid_response)
        self._i2c_initialized: bool = False

        # List of async functions to run for hardware setup/recovery
        self._setup_hooks: List[Callable[[], Awaitable[None]]] = []

        # Store I2C pins for recovery
        self._sda_pin: int = 21
        self._scl_pin: int = 22

        # Components
        self._sensors: Dict[int, Sensor] = {}

    async def _run_setup_hooks(self) -> None:
        """Executes all registered setup hooks in parallel."""
        if not self._setup_hooks:
            return

        logger.debug(
            f"Executing {len(self._setup_hooks)} setup hooks for '{self.display_name}'..."
        )
        await asyncio.gather(*(hook() for hook in self._setup_hooks))

    async def _initialize(self) -> None:
        """Initializes all hardware components."""
        logger.info(f"SerialDevice '{self.display_name}' initializing...")
        await self._run_setup_hooks()
        self._initialized = True
        logger.info(f"SerialDevice '{self.display_name}' system ready.")

    async def _recover(self) -> None:
        """Recovery sequence after a device reboot."""
        logger.warning(
            f"SerialDevice '{self.display_name}' starting recovery sequence..."
        )

        # 1. Re-initialize I2C if it was previously used
        if self._i2c_initialized:
            await self.initialize_i2c(self._sda_pin, self._scl_pin)

        # 2. Re-run all component setup hooks (this will also restore servo positions)
        await self._run_setup_hooks()

        logger.info(f"SerialDevice '{self.display_name}' recovery complete.")

    def _handle_no_qid_response(self, response: str) -> None:
        """
        IntegratedDeviceからのレスポンスを受け取るシリアルワーカー向けのコールバック関数.
        """
        logger.debug(f"Response from device '{self.display_name}' : '{response}'")
        parts = response.split(":")
        if not parts:
            return

        msg = parts[0]
        if msg == "READY":
            logger.debug(
                f"Device system is ready (reboot detected) on '{self.display_name}'"
            )
            if not self._initialized:
                asyncio.create_task(self._initialize())
            else:
                asyncio.create_task(self._recover())
        elif msg == "RECV":
            # RECV:pin:count
            if len(parts) >= 3:
                try:
                    pin = int(parts[1])
                    count = int(parts[2])
                    if pin in self._sensors:
                        self._sensors[pin].notify(count)
                except ValueError:
                    logger.warning(f"Invalid RECV message on '{self.display_name}': {response}")

    # センサー初期化
    async def create_sensor(
        self, pin: int, callback: Callable[[int], None], debounce: int = 50
    ) -> Sensor:
        """Creates and configures a sensor on the specified pin."""

        async def setup_hook() -> None:
            """Sends configuration for the sensor."""
            command = f"SETSENS:{pin}:{debounce}"
            try:
                response = await self._worker.send(command)
                if response != "SETSENS_OK":
                    logger.warning(
                        f"Failed to configure sensor (pin {pin}): {response}"
                    )
            except Exception as e:
                logger.error(f"Error during setup hook for sensor pin {pin}: {e}")

        # Register hook for future recovery
        self._setup_hooks.append(setup_hook)

        # Initial configuration
        await setup_hook()

        # Create and store sensor
        sensor = Sensor(read_handler=callback)
        self._sensors[pin] = sensor
        return sensor

    # I2Cセットアップ関連
    async def initialize_i2c(self, sda_pin: int, scl_pin: int) -> None:
        self._sda_pin = sda_pin
        self._scl_pin = scl_pin
        command = f"INIT_I2C:{sda_pin}:{scl_pin}"

        try:
            response = await self._worker.send(command)
            if response == "I2C_OK":
                self._i2c_initialized = True
                logger.info(f"I2C initialized successfully on '{self.display_name}'.")
            else:
                logger.warning(
                    f"I2C initialization failed on '{self.display_name}': {response}"
                )
                raise exceptions.hardware.SerialError(f"I2C initialization failed: {response}")
        except Exception as e:
            logger.error(
                f"Error during I2C initialization on '{self.display_name}': {e}"
            )
            raise

    # [総合]サーボ制御
    async def _control_servo(
        self, mode: int, servo_id: int, value: int, dur: int, address: int
    ) -> str:
        command = f"DIRECT:{mode}:{servo_id}:{value}:{dur}:{address}"

        try:
            response = await self._worker.send(command)
            return response
        except Exception as e:
            logger.error(
                f"Servo command failed for '{self.display_name}' (ID: {servo_id}): {e}"
            )
            raise exceptions.hardware.SerialError(
                f"Servo command failed for '{self.display_name}' (ID: {servo_id}): {e}"
            )

    # [I2C]サーボ初期化
    async def create_PCA9685_servo(
        self, I2C_address: int, PCA9685_pin: int
    ) -> Actuator:
        if not self._i2c_initialized:
            raise exceptions.hardware.SerialI2CNotInitializedError(
                f"I2C is not initialized on '{self.display_name}'."
            )

        async def move_handler(value: int) -> None:
            """Internal handler to send move commands."""
            await self._control_servo(
                mode=1, servo_id=PCA9685_pin, value=value, dur=300, address=I2C_address
            )

        # Create instance first to be captured by setup_hook
        servo = Actuator(move_handler=move_handler)

        async def setup_hook() -> None:
            """Sends configuration and restores position if known."""
            # 1. Hardware Configuration
            command = f"SETCFG:1:{PCA9685_pin}:0:{I2C_address}"
            try:
                response = await self._worker.send(command)
                if response != "SETCFG_OK":
                    logger.warning(
                        f"Failed to configure PCA9685 servo (pin {PCA9685_pin}): {response}"
                    )
                    return

                # 2. Restore Last Position
                if servo.last_value is not None:
                    logger.info(
                        f"Restoring servo pin {PCA9685_pin} to {servo.last_value}"
                    )
                    # Use internal _control_servo to avoid resetting last_value
                    await move_handler(servo.last_value)

            except Exception as e:
                logger.error(
                    f"Error during setup hook for servo pin {PCA9685_pin}: {e}"
                )

        # Register hook for future recovery
        self._setup_hooks.append(setup_hook)

        # Initial configuration
        await setup_hook()

        return servo
