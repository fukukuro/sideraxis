from __future__ import annotations
import asyncio
from dataclasses import dataclass
from typing import Optional, Union, List, Tuple, TYPE_CHECKING, Any, Dict
from infrastructure.logger import logger
import exceptions.core

if TYPE_CHECKING:
    from .PRDMS4 import PRDMS4
    from .place import Place, Occupancy, OccupyTransaction

@dataclass
class AllocatePlaces:
    places: list[int]  # Indices in _train_places

@dataclass
class WaitForVTime:
    v_time: float

@dataclass
class WaitForVClock:
    v_clock: float

@dataclass
class WaitForPlaceArrival:
    index: int  # Index in _train_places

@dataclass
class WaitForFlag:
    flag_id: int
    value: int

@dataclass
class SetFlag:
    flag_id: int
    value: int

@dataclass
class TrainTerminate:
    pass

TrainActions = Union[AllocatePlaces, WaitForVTime, WaitForVClock, WaitForPlaceArrival, WaitForFlag, SetFlag, TrainTerminate]


class Train:
    def __init__(self, display_name: str = "Unknown Train"):
        self.display_name = display_name
        self._train_place_index: Optional[Tuple[int, ...]] = None  # Indices in _train_places
        self._train_places: list[int] = []  # List of Place IDs in PRDMS4._places
        self.stab: list[TrainActions] = []  # Actions to perform
        self.is_active: bool = False
        self.error_message: Optional[str] = None
        self._arrival_events: Dict[int, asyncio.Event] = {}

    def set_itinerary(self, places: List[int], initial_index: Tuple[int, ...] = (0,)):
        """Sets the planned route for the train."""
        self._train_places = places
        self._train_place_index = initial_index

    async def process_stub(self, prdms: "PRDMS4"):
        """Processes the train's stub actions."""
        from .place import Occupancy, OccupyTransaction

        self.is_active = True
        logger.info(f"Train '{self.display_name}' starting stub processing.")
        try:
            while self.stab and self.is_active:
                action = self.stab[0]
                if isinstance(action, AllocatePlaces):
                    target_place_indices = [self._train_places[idx] for idx in action.places]
                    target_places = [prdms._places[idx] for idx in target_place_indices]

                    try:
                        transaction = OccupyTransaction(
                            [(p, Occupancy(occupier=self)) for p in target_places]
                        )
                        transaction.execute()
                        logger.debug(f"Train '{self.display_name}' allocated places: {target_place_indices}")
                        self.stab.pop(0)
                    except exceptions.core.PlaceAlreadyOccupiedError:
                        await asyncio.sleep(1)
                elif isinstance(action, WaitForVTime):
                    logger.debug(f"Train '{self.display_name}' waiting for v_time: {action.v_time}")
                    await asyncio.sleep(action.v_time / prdms._v_clock.rate)
                    self.stab.pop(0)
                elif isinstance(action, WaitForVClock):
                    logger.debug(f"Train '{self.display_name}' waiting for v_clock: {action.v_clock}")
                    while prdms._v_clock.getVclockTime() < action.v_clock:
                        await asyncio.sleep(0.1)
                    self.stab.pop(0)
                elif isinstance(action, WaitForPlaceArrival):
                    logger.debug(f"Train '{self.display_name}' waiting for arrival at itinerary index: {action.index}")
                    if action.index not in self._arrival_events:
                        self._arrival_events[action.index] = asyncio.Event()
                    
                    # Check if already there or past it
                    if self._train_place_index and any(idx >= action.index for idx in self._train_place_index):
                        self._arrival_events[action.index].set()
                    
                    await self._arrival_events[action.index].wait()
                    self.stab.pop(0)
                elif isinstance(action, WaitForFlag):
                    logger.debug(f"Train '{self.display_name}' waiting for flag {action.flag_id} == {action.value}")
                    # Simple polling for flags for now, could use a listener in FlagManager
                    while prdms._flag_manager.get_flag(action.flag_id) != action.value:
                        await asyncio.sleep(0.5)
                    self.stab.pop(0)
                elif isinstance(action, SetFlag):
                    logger.debug(f"Train '{self.display_name}' setting flag {action.flag_id} to {action.value}")
                    prdms._flag_manager.set_flag(action.flag_id, action.value)
                    self.stab.pop(0)
                elif isinstance(action, TrainTerminate):
                    logger.info(f"Train '{self.display_name}' terminating.")
                    self.is_active = False
                    self.stab.pop(0)
                    # Release all places
                    if self._train_place_index:
                        release_list = []
                        for idx in self._train_place_index:
                            place_id = self._train_places[idx]
                            release_list.append((prdms._places[place_id], None))
                        OccupyTransaction(release_list).execute()
                        self._train_place_index = None
        except Exception as e:
            self.error_message = str(e)
            logger.error(f"Error in stub processing for '{self.display_name}': {e}")
        finally:
            self.is_active = False
            logger.info(f"Train '{self.display_name}' finished stub processing.")

    def stop(self):
        """Stops the stub processing."""
        self.is_active = False

    def handle_sensor_event(self, prdms: "PRDMS4", place_id: int, count: int):
        """
        Updates the train's position based on sensor pulses.
        count=1: Entry (spanning current and next place)
        count=2: Exit (completely in next place, release old place)
        """
        from .place import OccupyTransaction

        if self._train_place_index is None:
            return

        # Check if the place_id is the 'next' expected place in the itinerary
        last_idx = max(self._train_place_index)
        if last_idx + 1 >= len(self._train_places):
            logger.warning(f"Train '{self.display_name}' received sensor for end of itinerary.")
            return

        expected_next_place_id = self._train_places[last_idx + 1]

        if place_id == expected_next_place_id:
            if count == 1:  # Entry
                # Now spanning both places
                new_idx = last_idx + 1
                self._train_place_index = tuple(sorted(set(self._train_place_index) | {new_idx}))
                logger.info(f"Train '{self.display_name}' entering place {place_id} (index {new_idx}). Positions: {self._train_place_index}")
                
                # Notify anyone waiting for THIS SPECIFIC index arrival
                if new_idx in self._arrival_events:
                    self._arrival_events[new_idx].set()
            elif count == 2:  # Exit
                # Cleared the previous place(s)
                old_indices = [idx for idx in self._train_place_index if idx <= last_idx]
                self._train_place_index = (last_idx + 1,)
                
                # Release old places
                release_list = []
                for idx in old_indices:
                    old_place_id = self._train_places[idx]
                    release_list.append((prdms._places[old_place_id], None))
                
                OccupyTransaction(release_list).execute()
                logger.info(f"Train '{self.display_name}' exited to place {place_id}. Released: {[self._train_places[i] for i in old_indices]}")
                # Cleared the previous place(s)
                old_indices = [idx for idx in self._train_place_index if idx <= last_idx]
                self._train_place_index = (last_idx + 1,)
                
                # Release old places
                release_list = []
                for idx in old_indices:
                    old_place_id = self._train_places[idx]
                    release_list.append((prdms._places[old_place_id], None))
                
                OccupyTransaction(release_list).execute()
                logger.info(f"Train '{self.display_name}' exited to place {place_id}. Released: {[self._train_places[i] for i in old_indices]}")

    def get_status(self) -> dict:
        """Returns a snapshot of the train's status."""
        return {
            "display_name": self.display_name,
            "current_positions": self._train_place_index,
            "itinerary": self._train_places,
            "is_active": self.is_active,
            "remaining_actions": len(self.stab),
            "error": self.error_message,
        }
