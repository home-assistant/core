"""Test the UniFi Protect lock platform."""
# pylint: disable=protected-access
from __future__ import annotations

from copy import copy
from unittest.mock import AsyncMock, Mock

import pytest
from pyunifiprotect.data import Doorlock, LockStatusType

from homeassistant.components.unifiprotect.const import DEFAULT_ATTRIBUTION
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_ENTITY_ID,
    STATE_JAMMED,
    STATE_LOCKED,
    STATE_LOCKING,
    STATE_UNAVAILABLE,
    STATE_UNLOCKED,
    STATE_UNLOCKING,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MockEntityFixture, assert_entity_counts


@pytest.fixture(name="doorlock")
async def doorlock_fixture(
    hass: HomeAssistant, mock_entry: MockEntityFixture, mock_doorlock: Doorlock
):
    """Fixture for a single doorlock for testing the lock platform."""

    # disable pydantic validation so mocking can happen
    Doorlock.__config__.validate_assignment = False

    lock_obj = mock_doorlock.copy()
    lock_obj._api = mock_entry.api
    lock_obj.name = "Test Lock"
    lock_obj.lock_status = LockStatusType.OPEN

    mock_entry.api.bootstrap.doorlocks = {
        lock_obj.id: lock_obj,
    }

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    assert_entity_counts(hass, Platform.LOCK, 1, 1)

    yield (lock_obj, "lock.test_lock_lock")

    Doorlock.__config__.validate_assignment = True


async def test_lock_setup(
    hass: HomeAssistant,
    doorlock: tuple[Doorlock, str],
):
    """Test lock entity setup."""

    unique_id = f"{doorlock[0].mac}_lock"
    entity_id = doorlock[1]

    entity_registry = er.async_get(hass)
    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == unique_id

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNLOCKED
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_lock_locked(
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    doorlock: tuple[Doorlock, str],
):
    """Test lock entity locked."""

    new_bootstrap = copy(mock_entry.api.bootstrap)
    new_lock = doorlock[0].copy()
    new_lock.lock_status = LockStatusType.CLOSED

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_lock

    new_bootstrap.doorlocks = {new_lock.id: new_lock}
    mock_entry.api.bootstrap = new_bootstrap
    mock_entry.api.ws_subscription(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(doorlock[1])
    assert state
    assert state.state == STATE_LOCKED


async def test_lock_unlocking(
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    doorlock: tuple[Doorlock, str],
):
    """Test lock entity unlocking."""

    new_bootstrap = copy(mock_entry.api.bootstrap)
    new_lock = doorlock[0].copy()
    new_lock.lock_status = LockStatusType.OPENING

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_lock

    new_bootstrap.doorlocks = {new_lock.id: new_lock}
    mock_entry.api.bootstrap = new_bootstrap
    mock_entry.api.ws_subscription(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(doorlock[1])
    assert state
    assert state.state == STATE_UNLOCKING


async def test_lock_locking(
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    doorlock: tuple[Doorlock, str],
):
    """Test lock entity locking."""

    new_bootstrap = copy(mock_entry.api.bootstrap)
    new_lock = doorlock[0].copy()
    new_lock.lock_status = LockStatusType.CLOSING

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_lock

    new_bootstrap.doorlocks = {new_lock.id: new_lock}
    mock_entry.api.bootstrap = new_bootstrap
    mock_entry.api.ws_subscription(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(doorlock[1])
    assert state
    assert state.state == STATE_LOCKING


async def test_lock_jammed(
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    doorlock: tuple[Doorlock, str],
):
    """Test lock entity jammed."""

    new_bootstrap = copy(mock_entry.api.bootstrap)
    new_lock = doorlock[0].copy()
    new_lock.lock_status = LockStatusType.JAMMED_WHILE_CLOSING

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_lock

    new_bootstrap.doorlocks = {new_lock.id: new_lock}
    mock_entry.api.bootstrap = new_bootstrap
    mock_entry.api.ws_subscription(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(doorlock[1])
    assert state
    assert state.state == STATE_JAMMED


async def test_lock_unavailable(
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    doorlock: tuple[Doorlock, str],
):
    """Test lock entity unavailable."""

    new_bootstrap = copy(mock_entry.api.bootstrap)
    new_lock = doorlock[0].copy()
    new_lock.lock_status = LockStatusType.NOT_CALIBRATED

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_lock

    new_bootstrap.doorlocks = {new_lock.id: new_lock}
    mock_entry.api.bootstrap = new_bootstrap
    mock_entry.api.ws_subscription(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(doorlock[1])
    assert state
    assert state.state == STATE_UNAVAILABLE


async def test_lock_do_lock(
    hass: HomeAssistant,
    doorlock: tuple[Doorlock, str],
):
    """Test lock entity lock service."""

    doorlock[0].__fields__["close_lock"] = Mock()
    doorlock[0].close_lock = AsyncMock()

    await hass.services.async_call(
        "lock",
        "lock",
        {ATTR_ENTITY_ID: doorlock[1]},
        blocking=True,
    )

    doorlock[0].close_lock.assert_called_once()


async def test_lock_do_unlock(
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    doorlock: tuple[Doorlock, str],
):
    """Test lock entity unlock service."""

    new_bootstrap = copy(mock_entry.api.bootstrap)
    new_lock = doorlock[0].copy()
    new_lock.lock_status = LockStatusType.CLOSED

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_lock

    new_bootstrap.doorlocks = {new_lock.id: new_lock}
    mock_entry.api.bootstrap = new_bootstrap
    mock_entry.api.ws_subscription(mock_msg)
    await hass.async_block_till_done()

    new_lock.__fields__["open_lock"] = Mock()
    new_lock.open_lock = AsyncMock()

    await hass.services.async_call(
        "lock",
        "unlock",
        {ATTR_ENTITY_ID: doorlock[1]},
        blocking=True,
    )

    new_lock.open_lock.assert_called_once()
