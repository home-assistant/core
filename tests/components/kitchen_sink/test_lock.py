"""The tests for the kitchen_sink lock platform."""

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.kitchen_sink import DOMAIN
from homeassistant.components.lock import (
    DOMAIN as LOCK_DOMAIN,
    SERVICE_LOCK,
    SERVICE_OPEN,
    SERVICE_UNLOCK,
    STATE_LOCKED,
    STATE_LOCKING,
    STATE_UNLOCKED,
    STATE_UNLOCKING,
)
from homeassistant.const import ATTR_ENTITY_ID, EVENT_STATE_CHANGED, Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import async_capture_events, async_mock_service

LOCKED_LOCK = "lock.basic_lock"
OPENABLE_LOCK = "lock.openable_lock"
UNLOCKED_LOCK = "lock.another_basic_lock"


@pytest.fixture
async def lock_only() -> None:
    """Enable only the lock platform."""
    with patch(
        "homeassistant.components.kitchen_sink.COMPONENTS_WITH_DEMO_PLATFORM",
        [Platform.LOCK],
    ):
        yield


@pytest.fixture(autouse=True)
async def setup_comp(hass: HomeAssistant, lock_only):
    """Set up demo component."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()


async def test_states(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Test the expected lock entities are added."""
    states = hass.states.async_all()
    assert set(states) == snapshot


async def test_locking(hass: HomeAssistant) -> None:
    """Test the locking of a lock."""
    state = hass.states.get(UNLOCKED_LOCK)
    assert state.state == STATE_UNLOCKED
    await hass.async_block_till_done()

    state_changes = async_capture_events(hass, EVENT_STATE_CHANGED)
    await hass.services.async_call(
        LOCK_DOMAIN, SERVICE_LOCK, {ATTR_ENTITY_ID: UNLOCKED_LOCK}, blocking=False
    )
    await hass.async_block_till_done()

    assert state_changes[0].data["entity_id"] == UNLOCKED_LOCK
    assert state_changes[0].data["new_state"].state == STATE_LOCKING

    assert state_changes[1].data["entity_id"] == UNLOCKED_LOCK
    assert state_changes[1].data["new_state"].state == STATE_LOCKED


async def test_unlocking(hass: HomeAssistant) -> None:
    """Test the unlocking of a lock."""
    state = hass.states.get(LOCKED_LOCK)
    assert state.state == STATE_LOCKED
    await hass.async_block_till_done()

    state_changes = async_capture_events(hass, EVENT_STATE_CHANGED)
    await hass.services.async_call(
        LOCK_DOMAIN, SERVICE_UNLOCK, {ATTR_ENTITY_ID: LOCKED_LOCK}, blocking=False
    )
    await hass.async_block_till_done()

    assert state_changes[0].data["entity_id"] == LOCKED_LOCK
    assert state_changes[0].data["new_state"].state == STATE_UNLOCKING

    assert state_changes[1].data["entity_id"] == LOCKED_LOCK
    assert state_changes[1].data["new_state"].state == STATE_UNLOCKED


async def test_opening_mocked(hass: HomeAssistant) -> None:
    """Test the opening of a lock."""
    calls = async_mock_service(hass, LOCK_DOMAIN, SERVICE_OPEN)
    await hass.services.async_call(
        LOCK_DOMAIN, SERVICE_OPEN, {ATTR_ENTITY_ID: OPENABLE_LOCK}, blocking=True
    )
    assert len(calls) == 1


async def test_opening(hass: HomeAssistant) -> None:
    """Test the opening of a lock."""
    await hass.services.async_call(
        LOCK_DOMAIN, SERVICE_OPEN, {ATTR_ENTITY_ID: OPENABLE_LOCK}, blocking=True
    )
    state = hass.states.get(OPENABLE_LOCK)
    assert state.state == STATE_UNLOCKED
