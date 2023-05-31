"""The tests for the Demo lock platform."""
from unittest.mock import patch

import pytest

from homeassistant.components.demo import DOMAIN, lock as demo_lock
from homeassistant.components.lock import (
    DOMAIN as LOCK_DOMAIN,
    SERVICE_LOCK,
    SERVICE_OPEN,
    SERVICE_UNLOCK,
    STATE_JAMMED,
    STATE_LOCKED,
    STATE_LOCKING,
    STATE_UNLOCKED,
    STATE_UNLOCKING,
)
from homeassistant.const import ATTR_ENTITY_ID, EVENT_STATE_CHANGED
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import async_capture_events, async_mock_service

FRONT = "lock.front_door"
KITCHEN = "lock.kitchen_door"
POORLY_INSTALLED = "lock.poorly_installed_door"
OPENABLE_LOCK = "lock.openable_lock"


@pytest.fixture(autouse=True)
async def setup_comp(hass):
    """Set up demo component."""
    assert await async_setup_component(
        hass, LOCK_DOMAIN, {LOCK_DOMAIN: {"platform": DOMAIN}}
    )
    await hass.async_block_till_done()


@patch.object(demo_lock, "LOCK_UNLOCK_DELAY", 0)
async def test_locking(hass: HomeAssistant) -> None:
    """Test the locking of a lock."""
    state = hass.states.get(KITCHEN)
    assert state.state == STATE_UNLOCKED
    await hass.async_block_till_done()

    state_changes = async_capture_events(hass, EVENT_STATE_CHANGED)
    await hass.services.async_call(
        LOCK_DOMAIN, SERVICE_LOCK, {ATTR_ENTITY_ID: KITCHEN}, blocking=False
    )
    await hass.async_block_till_done()

    assert state_changes[0].data["entity_id"] == KITCHEN
    assert state_changes[0].data["new_state"].state == STATE_LOCKING

    assert state_changes[1].data["entity_id"] == KITCHEN
    assert state_changes[1].data["new_state"].state == STATE_LOCKED


@patch.object(demo_lock, "LOCK_UNLOCK_DELAY", 0)
async def test_unlocking(hass: HomeAssistant) -> None:
    """Test the unlocking of a lock."""
    state = hass.states.get(FRONT)
    assert state.state == STATE_LOCKED
    await hass.async_block_till_done()

    state_changes = async_capture_events(hass, EVENT_STATE_CHANGED)
    await hass.services.async_call(
        LOCK_DOMAIN, SERVICE_UNLOCK, {ATTR_ENTITY_ID: FRONT}, blocking=False
    )
    await hass.async_block_till_done()

    assert state_changes[0].data["entity_id"] == FRONT
    assert state_changes[0].data["new_state"].state == STATE_UNLOCKING

    assert state_changes[1].data["entity_id"] == FRONT
    assert state_changes[1].data["new_state"].state == STATE_UNLOCKED


@patch.object(demo_lock, "LOCK_UNLOCK_DELAY", 0)
async def test_jammed_when_locking(hass: HomeAssistant) -> None:
    """Test the locking of a lock jams."""
    state = hass.states.get(POORLY_INSTALLED)
    assert state.state == STATE_UNLOCKED
    await hass.async_block_till_done()

    state_changes = async_capture_events(hass, EVENT_STATE_CHANGED)
    await hass.services.async_call(
        LOCK_DOMAIN, SERVICE_LOCK, {ATTR_ENTITY_ID: POORLY_INSTALLED}, blocking=False
    )
    await hass.async_block_till_done()

    assert state_changes[0].data["entity_id"] == POORLY_INSTALLED
    assert state_changes[0].data["new_state"].state == STATE_LOCKING

    assert state_changes[1].data["entity_id"] == POORLY_INSTALLED
    assert state_changes[1].data["new_state"].state == STATE_JAMMED


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
