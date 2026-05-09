from __future__ import annotations

from typing import Awaitable, Callable, Optional

from infrastructure.task_delegator import TaskDelegator


class Actuator:
    def __init__(self, move_handler: Callable[[int], Awaitable[None]], display_name: str = ""):
        self._move_handler = move_handler
        # Stores the last commanded value for recovery
        self.last_value: Optional[int] = None
        self.moved_by_only_human = False
        self.display_name = display_name

    def callback(self, response: str) -> None:
        """Called when a serial response for a move command is received."""
        pass

    async def move(self, value: int) -> None:
        """Updates the state and sends the move command to the hardware."""
        self.last_value = value
        await self._move_handler(value)

class Sensor:
    def __init__(self, read_handler: Callable[[int], None]):
        self._read_handler = read_handler

    def notify(self, value: int):
        self._read_handler(value)

class ManualActuator:
    def __init__(self, display_name: str, manual_task_manager: TaskDelegator):
        self._manual_task_manager = manual_task_manager
        self.display_name = display_name
        self._generic_servo = Actuator(move_handler=self.move_to_degree, display_name=display_name)

    async def move_to_degree(self, degree: int):
        await self._manual_task_manager.issue_task_and_wait(
            f"マニュアルアクチュエータ'{self.display_name}'を角度'{degree}'に転換してください"
        )
        pass

    @property
    def generic_servo(self):
        return self._generic_servo
