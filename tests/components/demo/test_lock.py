"""The tests for the Demo lock platform."""
import pytest

from homeassistant.components.demo import DOMAIN
from homeassistant.components.lock import (
    DOMAIN as LOCK_DOMAIN,
    SERVICE_LOCK,
    SERVICE_OPEN,
    SERVICE_UNLOCK,
    STATE_LOCKED,
    STATE_UNLOCKED,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.setup import async_setup_component

from tests.common import async_mock_service

FRONT = "lock.front_door"
KITCHEN = "lock.kitchen_door"
OPENABLE_LOCK = "lock.openable_lock"


@pytest.fixture(autouse=True)
def setup_comp(hass):
    """Set up demo component."""
    hass.loop.run_until_complete(
        async_setup_component(hass, LOCK_DOMAIN, {LOCK_DOMAIN: {"platform": DOMAIN}})
    )


async def test_locking(hass):
    """Test the locking of a lock."""
    state = hass.states.get(KITCHEN)
    assert state.state == STATE_UNLOCKED

    await hass.services.async_call(
        LOCK_DOMAIN, SERVICE_LOCK, {ATTR_ENTITY_ID: KITCHEN}, blocking=True
    )

    state = hass.states.get(KITCHEN)
    assert state.state == STATE_LOCKED


async def test_unlocking(hass):
    """Test the unlocking of a lock."""
    state = hass.states.get(FRONT)
    assert state.state == STATE_LOCKED

    await hass.services.async_call(
        LOCK_DOMAIN, SERVICE_UNLOCK, {ATTR_ENTITY_ID: FRONT}, blocking=True
    )

    state = hass.states.get(FRONT)
    assert state.state == STATE_UNLOCKED


async def test_opening(hass):
    """Test the opening of a lock."""
    calls = async_mock_service(hass, LOCK_DOMAIN, SERVICE_OPEN)
    await hass.services.async_call(
        LOCK_DOMAIN, SERVICE_OPEN, {ATTR_ENTITY_ID: OPENABLE_LOCK}, blocking=True
    )
    assert len(calls) == 1
