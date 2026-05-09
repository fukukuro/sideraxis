import pytest
import asyncio
import logging
from core.place import Occupancy, OccupyTransaction
from core.stop_rail import StopRail, StopRailPosition

logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_stoprail_registration(mock_servo, places):
    logger.debug("Starting test")
    stop_rail = StopRail(mock_servo, 0, 90, (places[0], places[1]))
    for i, p in enumerate(places[:2]):
        logger.debug(f"Checking registration for place {i}")
        assert len(p._change_listeners) == 1

@pytest.mark.asyncio
async def test_stoprail_sync_movement(mock_servo, places, trains):
    logger.debug("Starting test")
    # STOP=0, GO=90
    stop_rail = StopRail(mock_servo, 0, 90, (places[0], places[1]))
    t1 = trains[0]
    
    logger.debug("Step 1: Occupy only one side (should stay STOP)")
    places[0].occupy(Occupancy(t1))
    await asyncio.sleep(0.1)
    
    logger.debug("Step 2: Occupy both sides (move to GO: 90)")
    tx = OccupyTransaction([
        (places[1], Occupancy(t1))
    ])
    tx.execute()
    await asyncio.sleep(0.1)
    mock_servo._move_handler.assert_called_with(90)
    
    logger.debug("Step 3: Release one side (move to STOP: 0)")
    places[0].release()
    await asyncio.sleep(0.1)
    mock_servo._move_handler.assert_called_with(0)
