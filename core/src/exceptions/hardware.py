from .base import PRDMS4Error

class CoreError(PRDMS4Error):
    "PRDMS4 Coreに関連するエラー"

    pass
class HardwareError(PRDMS4Error):
    "ハードウェアに関連するエラー"

    pass


class SerialError(HardwareError):
    "シリアル通信に関連するエラー"

    pass


class SerialPortNotOpenError(SerialError):
    "シリアルポートが未開放であるがゆえのエラー"

    pass


class SerialPortNotInitializedError(SerialError):
    "シリアルポートが初期化されていないゆえのエラー"

    pass


class SerialResponseTimeoutError(SerialError):
    "シリアル通信のレスポンスがタイムアウトした際のエラー"

    pass


class SerialI2CNotInitializedError(SerialError):
    "I2Cが初期化されていないゆえのエラー"

    pass
