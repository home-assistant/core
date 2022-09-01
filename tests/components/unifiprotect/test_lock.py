"""Test the UniFi Protect lock platform."""
# pylint: disable=protected-access
from __future__ import annotations

from unittest.mock import AsyncMock, Mock

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

from .utils import (
    MockUFPFixture,
    adopt_devices,
    assert_entity_counts,
    init_entry,
    remove_entities,
)


async def test_lock_remove(
    hass: HomeAssistant, ufp: MockUFPFixture, doorlock: Doorlock
):
    """Test removing and re-adding a lock device."""

    await init_entry(hass, ufp, [doorlock])
    assert_entity_counts(hass, Platform.LOCK, 1, 1)
    await remove_entities(hass, ufp, [doorlock])
    assert_entity_counts(hass, Platform.LOCK, 0, 0)
    await adopt_devices(hass, ufp, [doorlock])
    assert_entity_counts(hass, Platform.LOCK, 1, 1)


async def test_lock_setup(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorlock: Doorlock,
    unadopted_doorlock: Doorlock,
):
    """Test lock entity setup."""

    await init_entry(hass, ufp, [doorlock, unadopted_doorlock])
    assert_entity_counts(hass, Platform.LOCK, 1, 1)

    unique_id = f"{doorlock.mac}_lock"
    entity_id = "lock.test_lock_lock"

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
    ufp: MockUFPFixture,
    doorlock: Doorlock,
    unadopted_doorlock: Doorlock,
):
    """Test lock entity locked."""

    await init_entry(hass, ufp, [doorlock, unadopted_doorlock])
    assert_entity_counts(hass, Platform.LOCK, 1, 1)

    new_lock = doorlock.copy()
    new_lock.lock_status = LockStatusType.CLOSED

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_lock

    ufp.api.bootstrap.doorlocks = {new_lock.id: new_lock}
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get("lock.test_lock_lock")
    assert state
    assert state.state == STATE_LOCKED


async def test_lock_unlocking(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorlock: Doorlock,
    unadopted_doorlock: Doorlock,
):
    """Test lock entity unlocking."""

    await init_entry(hass, ufp, [doorlock, unadopted_doorlock])
    assert_entity_counts(hass, Platform.LOCK, 1, 1)

    new_lock = doorlock.copy()
    new_lock.lock_status = LockStatusType.OPENING

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_lock

    ufp.api.bootstrap.doorlocks = {new_lock.id: new_lock}
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get("lock.test_lock_lock")
    assert state
    assert state.state == STATE_UNLOCKING


async def test_lock_locking(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorlock: Doorlock,
    unadopted_doorlock: Doorlock,
):
    """Test lock entity locking."""

    await init_entry(hass, ufp, [doorlock, unadopted_doorlock])
    assert_entity_counts(hass, Platform.LOCK, 1, 1)

    new_lock = doorlock.copy()
    new_lock.lock_status = LockStatusType.CLOSING

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_lock

    ufp.api.bootstrap.doorlocks = {new_lock.id: new_lock}
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get("lock.test_lock_lock")
    assert state
    assert state.state == STATE_LOCKING


async def test_lock_jammed(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorlock: Doorlock,
    unadopted_doorlock: Doorlock,
):
    """Test lock entity jammed."""

    await init_entry(hass, ufp, [doorlock, unadopted_doorlock])
    assert_entity_counts(hass, Platform.LOCK, 1, 1)

    new_lock = doorlock.copy()
    new_lock.lock_status = LockStatusType.JAMMED_WHILE_CLOSING

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_lock

    ufp.api.bootstrap.doorlocks = {new_lock.id: new_lock}
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get("lock.test_lock_lock")
    assert state
    assert state.state == STATE_JAMMED


async def test_lock_unavailable(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorlock: Doorlock,
    unadopted_doorlock: Doorlock,
):
    """Test lock entity unavailable."""

    await init_entry(hass, ufp, [doorlock, unadopted_doorlock])
    assert_entity_counts(hass, Platform.LOCK, 1, 1)

    new_lock = doorlock.copy()
    new_lock.lock_status = LockStatusType.NOT_CALIBRATED

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_lock

    ufp.api.bootstrap.doorlocks = {new_lock.id: new_lock}
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get("lock.test_lock_lock")
    assert state
    assert state.state == STATE_UNAVAILABLE


async def test_lock_do_lock(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorlock: Doorlock,
    unadopted_doorlock: Doorlock,
):
    """Test lock entity lock service."""

    await init_entry(hass, ufp, [doorlock, unadopted_doorlock])
    assert_entity_counts(hass, Platform.LOCK, 1, 1)

    doorlock.__fields__["close_lock"] = Mock(final=False)
    doorlock.close_lock = AsyncMock()

    await hass.services.async_call(
        "lock",
        "lock",
        {ATTR_ENTITY_ID: "lock.test_lock_lock"},
        blocking=True,
    )

    doorlock.close_lock.assert_called_once()


async def test_lock_do_unlock(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorlock: Doorlock,
    unadopted_doorlock: Doorlock,
):
    """Test lock entity unlock service."""

    await init_entry(hass, ufp, [doorlock, unadopted_doorlock])
    assert_entity_counts(hass, Platform.LOCK, 1, 1)

    new_lock = doorlock.copy()
    new_lock.lock_status = LockStatusType.CLOSED

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_lock

    ufp.api.bootstrap.doorlocks = {new_lock.id: new_lock}
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()

    new_lock.__fields__["open_lock"] = Mock(final=False)
    new_lock.open_lock = AsyncMock()

    await hass.services.async_call(
        "lock",
        "unlock",
        {ATTR_ENTITY_ID: "lock.test_lock_lock"},
        blocking=True,
    )

    new_lock.open_lock.assert_called_once()
