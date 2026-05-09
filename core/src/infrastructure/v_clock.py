import datetime


class VClock:
    def __init__(self, origin_time: float, rate: int):
        self._origin_time = origin_time
        self._rate = rate

    def getVclockTime(self):
        now = datetime.datetime.now(datetime.timezone.utc).timestamp()
        return (now - self._origin_time) * self._rate
    def get_real_time_for_vclock(self,t:float):
        return t*self._rate
    @property
    def origin_time(self):
        return self._origin_time
    @property
    def rate(self):
        return self._rate