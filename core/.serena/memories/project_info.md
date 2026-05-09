# PICS (Plarail Interlocking & Control System) - Controler 1

## Purpose
Central control logic for an automated railway station using ESP32 and Python. It manages interlocking, manual tasks, and real-time monitoring of train positions.

## Tech Stack
- **Backend**: Python 3.13, FastAPI.
- **Hardware Interface**: Serial communication with ESP32 (custom protocol).
- **Frontend**: React (Vite, TypeScript, Shadcn UI).
- **Dependency Management**: `uv` (Python), `bun` (Frontend).
- **Testing**: `pytest`.
- **Linting/Formatting**: `ruff` (Python), `eslint` (Frontend).

## Codebase Structure
- `main.py`: FastAPI application entry point and system topology definition.
- `src/`:
    - `core/`: Domain models (Train, Place, StopRail, TwoWayPoint, FlagManager).
    - `hal/`: Hardware Abstraction Layer (SerialWorker, SerialGateway).
    - `web/`: FastAPI endpoints and controllers.
    - `infrastructure/`: Logging, VClock, and TaskDelegator.
- `frontend/`: Modern React dashboard.
- `firmware.cpp`: ESP32 source code (Arduino/RTOS).
- `tests/`: Automated tests.

## Style & Conventions
- **Naming**: Snake_case for Python, PascalCase for classes/components.
- **Type Hints**: Mandatory for Python backend.
- **Asynchronous**: Uses `asyncio` extensively for non-blocking I/O.

## Suggested Commands
- **Backend Run**: `uv run uvicorn main:app --reload`
- **Backend Test**: `uv run pytest tests`
- **Backend Lint**: `uv run ruff check .`
- **Frontend Run**: `cd frontend && bun dev`
- **Sync Dependencies**: `uv sync`
