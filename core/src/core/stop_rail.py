import asyncio
from enum import Enum
from typing import Tuple, Optional
from hal.component import Actuator
from core.place import Place, Occupancy

# 前提となるEnum定義 (インポートされている想定)
class StopRailPosition(Enum):
    STOP = 0
    GO = 1

class StopRail:
    def __init__(
        self,
        servo: Actuator,
        stop_position: int,
        go_position: int,
        places: Tuple[Place, Place]
    ) -> None:
        self._servo = servo
        self.stop_position = stop_position
        self.go_position = go_position
        self._places = places
        
        # 各Placeに自分を登録
        for p in self._places:
            p.add_change_listener(self._place_event_handler)

        # 同期用プリミティブ
        self._lock: asyncio.Lock = asyncio.Lock()
        self._sync_event: asyncio.Event = asyncio.Event()
        self._current_target: StopRailPosition = StopRailPosition.STOP

    async def _set_position(self, position: StopRailPosition) -> None:
        """実際のハードウェア動作"""
        target = self.stop_position if position == StopRailPosition.STOP else self.go_position
        await self._servo.move(target)

    async def _sync(self) -> None:
        # すでに移動処理中であれば、イベントフラグを立てて終了
        if self._lock.locked():
            self._sync_event.set()
            return

        async with self._lock:
            while True:
                # 占有状況からあるべき状態を判定
                def get_train(occ: Optional[Occupancy]):
                    return occ.occupier if occ is not None else None
                
                t0 = get_train(self._places[0].occupancy)
                t1 = get_train(self._places[1].occupancy)
                
                # 同じ列車が両方にまたがっている場合のみGO (空の場合はSTOP)
                new_target = StopRailPosition.GO if (
                    t0 is not None and t1 is not None and t0 == t1
                ) else StopRailPosition.STOP
                
                # ターゲットが変わったとき、または初回同期時に移動
                if new_target != self._current_target:
                    await self._set_position(new_target)
                    self._current_target = new_target
                
                # 移動完了後に、移動中に入ってきた更新予約（イベント）がないか確認
                if self._sync_event.is_set():
                    self._sync_event.clear()
                    # フラグがあればループを継続し、最新の占有状況で再評価
                    continue 
                else:
                    break
    
    def _place_event_handler(self, _=None) -> None:
        """イベントハンドラは非同期タスクを投げっぱなしにする"""
        asyncio.create_task(self._sync())