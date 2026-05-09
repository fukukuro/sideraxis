from src.core.PRDMS4 import PRDMS4
from src.infrastructure.v_clock import VClock
from src.web.api import get_api_app
from fastapi.middleware.cors import CORSMiddleware
import datetime

# 1. Initialize Infrastructure
# (example origin time and rate)
v_clock = VClock(datetime.datetime(2026, 3, 12, 21, 0, 0, 0).timestamp(), 10)

# 2. Initialize Service Layer
prdms = PRDMS4(v_clock=v_clock)

# 3. Create FastAPI App (as the entry point for uvicorn)

# --- Future setup would happen here (loading config, registering devices) ---
# For now, it's ready for requests.
app = get_api_app(prdms)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,   # 追記により追加
    allow_methods=["*"],      # 追記により追加
    allow_headers=["*"]       # 追記により追加
)