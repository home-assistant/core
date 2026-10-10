"""Test the Yale Access Bluetooth event entity."""

from collections.abc import Callable
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from yalexs_ble import (
    ConnectionInfo,
    DoorActivity,
    DoorStatus,
    LockActivity,
    LockInfo,
    LockOperationSource,
    LockState,
    LockStatus,
)
from yalexs_ble.const import LockOperationRemoteType

from homeassistant.components.yalexs_ble.const import (
    CONF_KEY,
    CONF_LOCAL_NAME,
    CONF_SLOT,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ADDRESS, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from . import YALE_ACCESS_LOCK_DISCOVERY_INFO

from tests.common import MockConfigEntry

ENTITY_ID = "event.mock_title_operation"


async def _setup_lock(
    hass: HomeAssistant,
) -> list[Callable[[DoorActivity | LockActivity], None]]:
    """Set up the integration with a mocked lock; return its activity callbacks."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_LOCAL_NAME: YALE_ACCESS_LOCK_DISCOVERY_INFO.name,
            CONF_ADDRESS: YALE_ACCESS_LOCK_DISCOVERY_INFO.address,
            CONF_KEY: "2fd51b8621c6a139eaffbedcb846b60f",
            CONF_SLOT: 66,
        },
        unique_id=YALE_ACCESS_LOCK_DISCOVERY_INFO.address,
    )
    entry.add_to_hass(hass)

    callbacks: list[Callable[[DoorActivity | LockActivity], None]] = []
    push_lock = MagicMock()
    push_lock.address = YALE_ACCESS_LOCK_DISCOVERY_INFO.address
    push_lock.start = AsyncMock(return_value=MagicMock())
    push_lock.wait_for_first_update = AsyncMock()
    push_lock.lock_state = LockState(
        lock=LockStatus.LOCKED,
        door=DoorStatus.CLOSED,
        battery=None,
        auth=None,
        auto_lock=None,
        auto_lock_prev=None,
    )
    push_lock.lock_info = LockInfo(
        manufacturer="Yale/August", model="ASL-03", serial="M1012LU", firmware="2.0"
    )
    push_lock.connection_info = ConnectionInfo(rssi=-60)
    push_lock.register_callback = MagicMock(return_value=lambda: None)

    def _register_activity_callback(
        callback: Callable[[DoorActivity | LockActivity], None],
    ) -> Callable[[], None]:
        callbacks.append(callback)
        return lambda: callbacks.remove(callback)

    push_lock.register_activity_callback = MagicMock(
        side_effect=_register_activity_callback
    )

    with (
        patch("homeassistant.components.yalexs_ble.close_stale_connections_by_address"),
        patch("homeassistant.components.yalexs_ble.PushLock", return_value=push_lock),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    return callbacks


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_lock_activity_is_delivered_as_an_event(hass: HomeAssistant) -> None:
    """A keypad unlock from the lock's activity log fires the event with its details."""
    callbacks = await _setup_lock(hass)
    assert len(callbacks) == 1
    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN

    when = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    callbacks[0](
        LockActivity(
            when,
            LockStatus.UNLOCKED,
            LockOperationSource.PIN,
            remote_type=None,
            slot=205,
        )
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state != STATE_UNKNOWN
    assert state.attributes["event_type"] == "activity"
    assert state.attributes["state"] == "lock_unlocked"
    assert state.attributes["attributes"] == {
        "timestamp": when,
        "source": "pin",
        "slot": 205,
    }


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_remote_and_door_activity_attributes(hass: HomeAssistant) -> None:
    """A remote lock carries its remote type; a door record carries only its time."""
    callbacks = await _setup_lock(hass)
    when = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)

    callbacks[0](
        LockActivity(
            when,
            LockStatus.LOCKED,
            LockOperationSource.REMOTE,
            remote_type=LockOperationRemoteType.BLE,
        )
    )
    await hass.async_block_till_done()
    attributes = hass.states.get(ENTITY_ID).attributes
    assert attributes["state"] == "lock_locked"
    assert attributes["attributes"] == {
        "timestamp": when,
        "source": "remote",
        "remote_type": "ble",
    }

    callbacks[0](DoorActivity(when, DoorStatus.OPENED))
    await hass.async_block_till_done()
    attributes = hass.states.get(ENTITY_ID).attributes
    assert attributes["state"] == "door_opened"
    assert attributes["attributes"] == {"timestamp": when}


async def test_event_entity_is_disabled_by_default(hass: HomeAssistant) -> None:
    """The entity, and with it the log reads, stays off until a user enables it."""
    callbacks = await _setup_lock(hass)
    assert hass.states.get(ENTITY_ID) is None
    assert callbacks == []
