import asyncio
from enum import Enum, auto
from typing import Tuple, Optional
from hal.component import Actuator
from core.place import Place, Occupancy
import exceptions

class TwoWayPointPosition(Enum):
    NORMAL = auto()
    REVERSE = auto()

class TwoWayPoint:
    def __init__(
        self,
        servo: Actuator,
        normal_position: int,
        reverse_position: int,
        places: Tuple[Place, Place, Place], # A, Normal先, Reverse先
    ) -> None:
        self._servo = servo
        self.normal_position = normal_position
        self.reverse_position = reverse_position
        self._places = places # 0: Base, 1: Normal, 2: Reverse
        
        # 各Placeに自分を登録
        for p in self._places:
            p.add_transaction_validator(self.validate_transaction)
            p.add_change_listener(self._place_event_handler)

        # 同期用プリミティブ
        self._lock: asyncio.Lock = asyncio.Lock()
        self._sync_event: asyncio.Event = asyncio.Event()
        self._current_target: TwoWayPointPosition = TwoWayPointPosition.NORMAL

    async def _move_servo(self, position: TwoWayPointPosition) -> None:
        """実際のハードウェア動作"""
        target = self.normal_position if position == TwoWayPointPosition.NORMAL else self.reverse_position
        await self._servo.move(target)

    def validate_transaction(self, places_and_occupiers: list[tuple[Place, Optional[Occupancy]]]):
        """
        ポイントに関連するPlaceの状態変化を抽出し、安全性を検証する。
        PlaceがNoneの場合は「空」として扱う。
        """
        # 1. 現在の自分の管轄プレイスの状態を把握
        # 処理対象のリストから、自分に関係あるプレイスの「新しい状態」を抽出する
        # ※未指定のプレイスは現状維持とみなすため、最初は現在値をコピーしておく
        new_states = {
            self._places[0]: self._places[0].occupancy,
            self._places[1]: self._places[1].occupancy,
            self._places[2]: self._places[2].occupancy
        }
        
        # リストの内容で「これから変わる状態」を更新
        for place, new_occ in places_and_occupiers:
            if place in new_states:
                new_states[place] = new_occ

        # 2. 判定用に列車の実体を抽出（T1, T2などが区別できるようにする）
        def get_train(occ: Optional[Occupancy]):
            return occ.occupier if occ is not None else None

        b_train = get_train(new_states[self._places[0]])
        n_train = get_train(new_states[self._places[1]])
        r_train = get_train(new_states[self._places[2]])

        # 3. 安全な状態の定義（真理値表に基づく判定）
        is_empty = (b_train is None and n_train is None and r_train is None)
        is_normal_route = (b_train is not None and b_train == n_train and r_train is None)
        is_reverse_route = (b_train is not None and b_train == r_train and n_train is None)

        # 許可リストにないものはすべてエラー
        if not (is_empty or is_normal_route or is_reverse_route):
            raise exceptions.core.PointSafetyViolationError(
                f"安全ではない進路が検出されました: Base={b_train}, Normal={n_train}, Reverse={r_train}. "
                "Baseに列車がある場合は、必ずNormalかReverseのどちらか一方に進路が確定している必要があります。"
            )

    async def _sync(self) -> None:
        """最新の状態を判定し、必要であればサーボを転換する"""
        if self._lock.locked():
            self._sync_event.set()
            return

        async with self._lock:
            while True:
                # --- ここにポイント転換のロジックを記述 ---
                # 例：列車がNORMAL側に行こうとしているか、REVERSE側に行こうとしているか判定
                base_occ = self._places[0].occupancy
                new_target = self._current_target
                
                def get_train(occ: Optional[Occupancy]):
                    return occ.occupier if occ is not None else None

                b_train = get_train(base_occ)
                n_train = get_train(self._places[1].occupancy)
                r_train = get_train(self._places[2].occupancy)

                # 判定例：BaseとNormal先が同じ列車ならNORMALへ
                if b_train is not None and b_train == n_train:
                    new_target = TwoWayPointPosition.NORMAL
                # 判定例：BaseとReverse先が同じ列車ならREVERSEへ
                elif b_train is not None and b_train == r_train:
                    new_target = TwoWayPointPosition.REVERSE
                
                # ターゲットが変わったときのみ移動
                if new_target != self._current_target:
                    await self._move_servo(new_target)
                    self._current_target = new_target
                
                # 移動完了後にイベントが溜まっていればループ（再評価）
                if self._sync_event.is_set():
                    self._sync_event.clear()
                    continue
                else:
                    break
    
    def _place_event_handler(self, _=None) -> None:
        """Placeの状態変化をトリガーに同期を開始"""
        asyncio.create_task(self._sync())