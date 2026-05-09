from __future__ import annotations

from typing import Optional, Callable
from dataclasses import dataclass
from core.train import Train
import exceptions


@dataclass
class Occupancy:
    occupier: Train

class Place:
    def __init__(self):
        self._occupancy: Optional[Occupancy] = None
        self._change_listeners:list[Callable[[],None]] = []
        self._transaction_validators:list[Callable[[list[tuple[Place,Optional[Occupancy]]]],None]] = []

    def occupy(self, occupancy: Occupancy):
        if self._occupancy is not None:
            raise exceptions.core.PlaceAlreadyOccupiedError()
        
        OccupyTransaction([(self, occupancy)]).execute()
        
    def internal_dangerously_change_occupancy(self, occupancy: Optional[Occupancy]):
        self._occupancy = occupancy

    def release(self):
        if self._occupancy is None:
            raise exceptions.core.PlaceNotOccupiedError()
        OccupyTransaction([(self, None)]).execute()

    @property
    def occupancy(self):
        return self._occupancy

    def add_change_listener(self, listener: Callable[[],None]):
        self._change_listeners.append(listener)
    
    def _notify_change(self):
        for listener in self._change_listeners:
            listener()
    
    def add_transaction_validator(self, validator: Callable[[list[tuple[Place,Optional[Occupancy]]]],None]):
        self._transaction_validators.append(validator)

class OccupyTransaction:
    def __init__(self,places_and_occupiers:list[tuple[Place,Optional[Occupancy]]]):
        self._places_and_occupiers = places_and_occupiers
    
    def execute(self):
        # 1. Validate with transaction validators (e.g., TwoWayPoint safety)
        for place,_ in self._places_and_occupiers:
            for validate in place._transaction_validators:
                validate(self._places_and_occupiers)
        
        # 2. Apply changes
        for place,occupancy in self._places_and_occupiers:
            place.internal_dangerously_change_occupancy(occupancy)
        
        # 3. Notify listeners
        for place,_ in self._places_and_occupiers:
            place._notify_change()