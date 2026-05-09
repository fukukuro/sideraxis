from fastapi import APIRouter
from core.PRDMS4 import PRDMS4


class VClockRouter:
    def __init__(self, PRDMS4:PRDMS4):
        self.PRDMS4 = PRDMS4
    def get_router(self):
        v_clock_router = APIRouter(prefix="/v_clock", tags=["v_clock"])
        r = v_clock_router
        @r.get("/")
        async def get_v_clock_detail():
            return {
                "origin_time": self.PRDMS4._v_clock.origin_time,
                "rate": self.PRDMS4._v_clock.rate,
            }
        return v_clock_router