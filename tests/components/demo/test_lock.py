"""The tests for the Demo lock platform."""
import pytest

from homeassistant.components import lock
from homeassistant.setup import async_setup_component

from tests.common import async_mock_service
from tests.components.lock import common

FRONT = "lock.front_door"
KITCHEN = "lock.kitchen_door"
OPENABLE_LOCK = "lock.openable_lock"


@pytest.fixture(autouse=True)
def setup_comp(hass):
    """Set up demo component."""
    hass.loop.run_until_complete(
        async_setup_component(hass, lock.DOMAIN, {lock.DOMAIN: {"platform": "demo"}})
    )


async def test_is_locked(hass):
    """Test if lock is locked."""
    assert lock.is_locked(hass, FRONT)
    assert hass.states.is_state(FRONT, "locked")

    assert not lock.is_locked(hass, KITCHEN)
    assert hass.states.is_state(KITCHEN, "unlocked")


async def test_locking(hass):
    """Test the locking of a lock."""
    await common.async_lock(hass, KITCHEN)
    assert lock.is_locked(hass, KITCHEN)


async def test_unlocking(hass):
    """Test the unlocking of a lock."""
    await common.async_unlock(hass, FRONT)
    assert not lock.is_locked(hass, FRONT)


async def test_opening(hass):
    """Test the opening of a lock."""
    calls = async_mock_service(hass, lock.DOMAIN, lock.SERVICE_OPEN)
    await common.async_open_lock(hass, OPENABLE_LOCK)
    await hass.async_block_till_done()
    assert len(calls) == 1
