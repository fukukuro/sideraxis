import pytest
from unittest.mock import AsyncMock
from core.place import Place
from core.PRDMS4 import Train
from hal.component import Actuator

@pytest.fixture
def mock_servo():
    move_handler = AsyncMock()
    return Actuator(move_handler=move_handler)

@pytest.fixture
def trains():
    return [Train() for _ in range(3)]

@pytest.fixture
def places():
    return [Place() for _ in range(3)]
