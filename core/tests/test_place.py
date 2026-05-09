import pytest
import logging
from core.place import Occupancy, OccupyTransaction
import exceptions

logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_place_occupy_and_release(places, trains):
    logger.debug("Starting test")
    p = places[0]
    t = trains[0]
    occ = Occupancy(occupier=t)
    
    logger.debug(f"Occupying place with train {t}")
    p.occupy(occ)
    assert p.occupancy == occ
    
    with pytest.raises(exceptions.core.PlaceAlreadyOccupiedError):
        logger.debug("Verifying Double-Occupancy error")
        p.occupy(occ)
        
    logger.debug("Releasing place")
    p.release()
    assert p.occupancy is None

@pytest.mark.asyncio
async def test_transaction_execution(places, trains):
    logger.debug("Starting test")
    t1 = trains[0]
    t2 = trains[1]
    
    tx = OccupyTransaction([
        (places[0], Occupancy(t1)),
        (places[1], Occupancy(t2))
    ])
    
    logger.debug("Executing transaction for multiple places")
    tx.execute()
    
    assert places[0].occupancy.occupier == t1
    assert places[1].occupancy.occupier == t2
