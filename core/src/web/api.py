from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from web.v_clock import VClockRouter
from core.PRDMS4 import PRDMS4
from web.hal import HalRouter
from web.core import CoreRouter
from web.infrastructure import InfrastructureRouter
import asyncio
import logging

logger = logging.getLogger(__name__)

class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.getMessage().find("GET /snapshot") == -1

logging.getLogger("uvicorn.access").addFilter(EndpointFilter())

def get_api_app(prdms: PRDMS4):
    app = FastAPI(title="PRDMS4 Control System")

    # Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(VClockRouter(prdms).get_router())
    app.include_router(HalRouter(prdms).get_router())
    app.include_router(CoreRouter(prdms).get_router())
    app.include_router(InfrastructureRouter(prdms).get_router())

    # System-wide Status Endpoints
    @app.get("/snapshot")
    async def get_snapshot():
        return prdms.get_system_snapshot()

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        try:
            while True:
                snapshot = prdms.get_system_snapshot()
                await websocket.send_json(snapshot)
                await asyncio.sleep(0.1)
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            try:
                await websocket.close()
            except:
                pass

    return app
