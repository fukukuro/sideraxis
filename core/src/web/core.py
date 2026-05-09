from fastapi import APIRouter, HTTPException
from core.PRDMS4 import PRDMS4
from core.place import Place
from pydantic import BaseModel
from typing import Optional, Tuple, List

# --- Place ---

class PlaceResponse(BaseModel):
    id: int
    occupier: Optional[str]

class PlaceRouter:
    def __init__(self, PRDMS4: PRDMS4):
        self.PRDMS4 = PRDMS4

    def get_router(self):
        place_router = APIRouter(prefix="/place", tags=["place"])
        r = place_router

        @r.get("/", response_model=list[PlaceResponse])
        async def get_places():
            places_list = []
            for idx, place in enumerate(self.PRDMS4._places):
                places_list.append({
                    "id": idx,
                    "occupier": place.occupancy.occupier.display_name if place.occupancy else None
                })
            return places_list

        @r.post("/")
        async def create_place():
            idx = self.PRDMS4.register_place(Place())
            return {"status": "success", "place_id": idx}

        return place_router

# --- Stop Rail ---

class StopRailCreationArgs(BaseModel):
    servo_id: int
    stop_position: int
    go_position: int
    place_ids: Tuple[int, int]

class StopRailResponse(BaseModel):
    id: int
    servo_id: int
    stop_position: int
    go_position: int
    place_ids: Tuple[int, int]

class StopRailRouter:
    def __init__(self, PRDMS4: PRDMS4):
        self.PRDMS4 = PRDMS4

    def get_router(self):
        router = APIRouter(prefix="/stop-rail", tags=["stop-rail"])

        @router.get("/", response_model=list[StopRailResponse])
        async def get_stop_rails():
            return [
                {"id": i, **meta} 
                for i, meta in enumerate(self.PRDMS4._stop_rail_metadata)
            ]

        @router.post("/")
        async def create_stop_rail(params: StopRailCreationArgs):
            try:
                idx = self.PRDMS4.create_stop_rail(
                    params.servo_id,
                    params.stop_position,
                    params.go_position,
                    params.place_ids
                )
                return {"status": "success", "stop_rail_id": idx}
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        return router

# --- Two Way Point ---

class TwoWayPointCreationArgs(BaseModel):
    servo_id: int
    normal_position: int
    reverse_position: int
    place_ids: Tuple[int, int, int]

class TwoWayPointResponse(BaseModel):
    id: int
    servo_id: int
    normal_position: int
    reverse_position: int
    place_ids: Tuple[int, int, int]

class TwoWayPointRouter:
    def __init__(self, PRDMS4: PRDMS4):
        self.PRDMS4 = PRDMS4

    def get_router(self):
        router = APIRouter(prefix="/two-way-point", tags=["two-way-point"])

        @router.get("/", response_model=list[TwoWayPointResponse])
        async def get_two_way_points():
            return [
                {"id": i, **meta} 
                for i, meta in enumerate(self.PRDMS4._two_way_point_metadata)
            ]

        @router.post("/")
        async def create_two_way_point(params: TwoWayPointCreationArgs):
            try:
                idx = self.PRDMS4.create_two_way_point(
                    params.servo_id,
                    params.normal_position,
                    params.reverse_position,
                    params.place_ids
                )
                return {"status": "success", "two_way_point_id": idx}
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        return router

# --- Train ---

class TrainCreationArgs(BaseModel):
    name: str
    itinerary: List[int]
    initial_index: List[int] = [0]
    actions: Optional[List[dict]] = None # List of action objects

class TrainResponse(BaseModel):
    display_name: str
    current_positions: Optional[Tuple[int, ...]]
    itinerary: List[int]
    is_active: bool
    remaining_actions: int
    error: Optional[str]

class TrainRouter:
    def __init__(self, PRDMS4: PRDMS4):
        self.PRDMS4 = PRDMS4

    def get_router(self):
        router = APIRouter(prefix="/train", tags=["train"])

        @router.get("/", response_model=list[TrainResponse])
        async def get_trains():
            return [t.get_status() for t in self.PRDMS4._trains]

        @router.post("/")
        async def create_train(params: TrainCreationArgs):
            # Convert dictionary actions to dataclass instances
            from core.train import AllocatePlaces, WaitForVTime, WaitForVClock, WaitForPlaceArrival, WaitForFlag, SetFlag, TrainTerminate
            
            stab_actions = []
            if params.actions:
                for a in params.actions:
                    a_type = a.get("type")
                    if a_type == "AllocatePlaces":
                        stab_actions.append(AllocatePlaces(places=a["places"]))
                    elif a_type == "WaitForVTime":
                        stab_actions.append(WaitForVTime(v_time=float(a["v_time"])))
                    elif a_type == "WaitForVClock":
                        stab_actions.append(WaitForVClock(v_clock=float(a["v_clock"])))
                    elif a_type == "WaitForPlaceArrival":
                        stab_actions.append(WaitForPlaceArrival(place_id=int(a["place_id"])))
                    elif a_type == "WaitForFlag":
                        stab_actions.append(WaitForFlag(flag_id=int(a["flag_id"]), value=int(a["value"])))
                    elif a_type == "SetFlag":
                        stab_actions.append(SetFlag(flag_id=int(a["flag_id"]), value=int(a["value"])))
                    elif a_type == "TrainTerminate":
                        stab_actions.append(TrainTerminate())

            train = self.PRDMS4.create_train(
                display_name=params.name,
                itinerary=params.itinerary,
                initial_index=tuple(params.initial_index),
                actions=stab_actions
            )
            return {"status": "success", "train": train.get_status()}

        return router

# --- Core Router ---

class CoreRouter:
    def __init__(self, PRDMS4: PRDMS4):
        self.PRDMS4 = PRDMS4

    def get_router(self):
        core_router = APIRouter(prefix="/core", tags=["core"])
        core_router.include_router(PlaceRouter(self.PRDMS4).get_router())
        core_router.include_router(StopRailRouter(self.PRDMS4).get_router())
        core_router.include_router(TwoWayPointRouter(self.PRDMS4).get_router())
        core_router.include_router(TrainRouter(self.PRDMS4).get_router())
        return core_router
