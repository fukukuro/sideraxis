from .base import PRDMS4Error

class CoreError(PRDMS4Error):
    "PRDMS4 Coreに関連するエラー"
    pass

class PlaceAlreadyOccupiedError(CoreError):
    "すでにそのPlaceが他の列車によって専有されているエラー"
    pass

class PlaceNotOccupiedError(CoreError):
    "そのPlaceが専有されていないにも関わらず解放しようとした際のエラー"
    pass

class PlaceOccupyErrorOfDependingPointsOrStopRails(CoreError):
    "そのPlaceに関連するStopRailまたはPointから変更が拒否された"
    pass

class InvalidPlaceStateForTwoWayPoint(CoreError):
    "syncなどの最中に現在の,TwoWayPointが購読するPointの状態を総合して,安全とは限らない状態であったためsync動作を中止しPlaceのロールバックを期待するエラー"

class PointSafetyViolationError(CoreError):
    "ポイントの連動制約違反(トランザクションの検証)"