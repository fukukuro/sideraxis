import pytest
import asyncio
import logging
from core.place import Occupancy, OccupyTransaction
from core.two_way_point import TwoWayPoint
import exceptions

logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_twowaypoint_registration(mock_servo, places):
    logger.debug("Starting test")
    point = TwoWayPoint(mock_servo, 10, 20, tuple(places))
    for i, p in enumerate(places):
        logger.debug(f"Checking registration for place {i}")
        assert len(p._transaction_validators) == 1
        assert len(p._change_listeners) == 1

@pytest.mark.asyncio
async def test_twowaypoint_validation_ok(mock_servo, places, trains):
    logger.debug("Starting test")
    point = TwoWayPoint(mock_servo, 10, 20, tuple(places))
    t1 = trains[0]
    
    logger.debug("Validating Empty state")
    point.validate_transaction([])
    
    logger.debug("Validating Normal route (Base + Normal)")
    point.validate_transaction([
        (places[0], Occupancy(t1)),
        (places[1], Occupancy(t1))
    ])
    
    logger.debug("Validating Reverse route (Base + Reverse)")
    point.validate_transaction([
        (places[0], Occupancy(t1)),
        (places[2], Occupancy(t1))
    ])

@pytest.mark.asyncio
async def test_twowaypoint_validation_error(mock_servo, places, trains):
    logger.debug("Starting test")
    point = TwoWayPoint(mock_servo, 10, 20, tuple(places))
    t1 = trains[0]
    t2 = trains[1]
    
    logger.debug("Checking error: Base occupied, output empty")
    with pytest.raises(exceptions.core.PointSafetyViolationError):
        point.validate_transaction([(places[0], Occupancy(t1))])
        
    logger.debug("Checking error: Base and Normal occupied by different trains")
    with pytest.raises(exceptions.core.PointSafetyViolationError):
        point.validate_transaction([
            (places[0], Occupancy(t1)),
            (places[1], Occupancy(t2))
        ])

@pytest.mark.asyncio
async def test_twowaypoint_sync_movement(mock_servo, places, trains):
    logger.debug("Starting test")
    # NORMAL=10, REVERSE=20
    point = TwoWayPoint(mock_servo, 10, 20, tuple(places))
    t1 = trains[0]
    
    logger.debug("Step 1: Path NORMAL (move_handler should not be called if default is NORMAL)")
    tx = OccupyTransaction([
        (places[0], Occupancy(t1)),
        (places[1], Occupancy(t1))
    ])
    tx.execute()
    await asyncio.sleep(0.1)
    
    logger.debug("Step 2: Change path to REVERSE (move to 20)")
    tx2 = OccupyTransaction([
        (places[1], None),
        (places[2], Occupancy(t1))
    ])
    tx2.execute()
    await asyncio.sleep(0.1)
    mock_servo._move_handler.assert_called_with(20)
    
    logger.debug("Step 3: Change path back to NORMAL (move to 10)")
    tx3 = OccupyTransaction([
        (places[1], Occupancy(t1)),
        (places[2], None)
    ])
    tx3.execute()
    await asyncio.sleep(0.1)
    mock_servo._move_handler.assert_called_with(10)
