"""The tests for the Demo lock platform."""
import asyncio

import pytest

from homeassistant.components.demo import DOMAIN
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
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.setup import async_setup_component

from tests.common import async_mock_service

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


async def test_locking(hass):
    """Test the locking of a lock."""
    state = hass.states.get(KITCHEN)
    assert state.state == STATE_UNLOCKED

    await hass.services.async_call(
        LOCK_DOMAIN, SERVICE_LOCK, {ATTR_ENTITY_ID: KITCHEN}, blocking=False
    )

    await asyncio.sleep(1)
    state = hass.states.get(KITCHEN)
    assert state.state == STATE_LOCKING
    await asyncio.sleep(2)
    state = hass.states.get(KITCHEN)
    assert state.state == STATE_LOCKED


async def test_unlocking(hass):
    """Test the unlocking of a lock."""
    state = hass.states.get(FRONT)
    assert state.state == STATE_LOCKED

    await hass.services.async_call(
        LOCK_DOMAIN, SERVICE_UNLOCK, {ATTR_ENTITY_ID: FRONT}, blocking=False
    )
    await asyncio.sleep(1)
    state = hass.states.get(FRONT)
    assert state.state == STATE_UNLOCKING
    await asyncio.sleep(2)
    state = hass.states.get(FRONT)
    assert state.state == STATE_UNLOCKED


async def test_jammed_when_locking(hass):
    """Test the locking of a lock jams."""
    state = hass.states.get(POORLY_INSTALLED)
    assert state.state == STATE_UNLOCKED

    await hass.services.async_call(
        LOCK_DOMAIN, SERVICE_LOCK, {ATTR_ENTITY_ID: POORLY_INSTALLED}, blocking=False
    )

    await asyncio.sleep(1)
    state = hass.states.get(POORLY_INSTALLED)
    assert state.state == STATE_LOCKING
    await asyncio.sleep(2)
    state = hass.states.get(POORLY_INSTALLED)
    assert state.state == STATE_JAMMED


async def test_opening_mocked(hass):
    """Test the opening of a lock."""
    calls = async_mock_service(hass, LOCK_DOMAIN, SERVICE_OPEN)
    await hass.services.async_call(
        LOCK_DOMAIN, SERVICE_OPEN, {ATTR_ENTITY_ID: OPENABLE_LOCK}, blocking=True
    )
    assert len(calls) == 1


async def test_opening(hass):
    """Test the opening of a lock."""
    await hass.services.async_call(
        LOCK_DOMAIN, SERVICE_OPEN, {ATTR_ENTITY_ID: OPENABLE_LOCK}, blocking=True
    )
    state = hass.states.get(OPENABLE_LOCK)
    assert state.state == STATE_UNLOCKED
