from typing import Dict, Callable, List

class FlagManager:
    def __init__(self):
        self._flags: Dict[int, int] = {}
        self._listeners: List[Callable[[int, int], None]] = []

    def set_flag(self, flag_id: int, value: int):
        self._flags[flag_id] = value
        for listener in self._listeners:
            listener(flag_id, value)

    def get_flag(self, flag_id: int) -> int:
        return self._flags.get(flag_id, 0) # Default to 0

    def add_listener(self, listener: Callable[[int, int], None]):
        self._listeners.append(listener)

    def get_all_flags(self) -> Dict[int, int]:
        return self._flags.copy()

