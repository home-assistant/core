"""Tests for the syncthing sensor platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from aiosyncthing.exceptions import SyncthingError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.syncthing.const import (
    DEVICE_CONNECTED_RECEIVED,
    DEVICE_DISCONNECTED_RECEIVED,
    DEVICE_PAUSED_RECEIVED,
    DEVICE_RESUMED_RECEIVED,
    DOMAIN,
    FOLDER_PAUSED_RECEIVED,
    FOLDER_SUMMARY_RECEIVED,
    INITIAL_EVENTS_READY,
    SERVER_AVAILABLE,
    SERVER_UNAVAILABLE,
    STATE_CHANGED_RECEIVED,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import dispatcher, entity_registry as er
from homeassistant.util import dt as dt_util

from . import (
    DEVICE_ENTITY_ID,
    DEVICE_ID,
    FOLDER_ENTITY_ID,
    FOLDER_ID,
    MOCK_DEVICE_CONNECTED_EVENT,
    MOCK_DEVICE_DISCONNECTED_EVENT,
    MOCK_DEVICE_PAUSED_EVENT,
    MOCK_DEVICE_RESUMED_EVENT,
    MOCK_FOLDER_PAUSED_EVENT,
    MOCK_FOLDER_STATUS,
    MOCK_FOLDER_SUMMARY_EVENT,
    MOCK_STATE_CHANGED_EVENT,
    SERVER_ID,
    create_mock_syncthing_client,
)

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform
from tests.typing import Any


async def test_sensor_platform_setup(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_syncthing: MagicMock,
) -> None:
    """Test sensor platform sets up folder and device sensors."""
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_sensor_platform_setup_fails_on_error(
    hass: HomeAssistant,
    entry: MockConfigEntry,
) -> None:
    """Test sensor platform setup fails when cannot get config."""
    mock_client = create_mock_syncthing_client()
    mock_client.system.config.side_effect = SyncthingError("Connection error")

    with patch(
        "homeassistant.components.syncthing.aiosyncthing.Syncthing",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(entry.entry_id)

        assert entry.state is ConfigEntryState.LOADED
        assert hass.states.get(FOLDER_ENTITY_ID) is None


async def test_device_sensor_processes_initial_events(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing: MagicMock,
) -> None:
    """Test device sensor processes initial events on startup."""
    syncthing = hass.data[DOMAIN][entry.entry_id]
    syncthing._initial_events = [
        MOCK_DEVICE_CONNECTED_EVENT,
        MOCK_DEVICE_PAUSED_EVENT,
        MOCK_DEVICE_DISCONNECTED_EVENT,
        MOCK_DEVICE_RESUMED_EVENT,
        MOCK_DEVICE_CONNECTED_EVENT,
        MOCK_DEVICE_DISCONNECTED_EVENT,
    ]

    dispatcher.async_dispatcher_send(
        hass,
        f"{INITIAL_EVENTS_READY}-{SERVER_ID}",
    )
    await hass.async_block_till_done()

    state = hass.states.get(DEVICE_ENTITY_ID)
    assert state is not None and state.state == "disconnected"


@pytest.mark.parametrize(
    ("events"),
    [
        ({}),
        ({DEVICE_CONNECTED_RECEIVED: MOCK_DEVICE_CONNECTED_EVENT}),
        ({DEVICE_DISCONNECTED_RECEIVED: MOCK_DEVICE_DISCONNECTED_EVENT}),
        ({DEVICE_PAUSED_RECEIVED: MOCK_DEVICE_PAUSED_EVENT}),
        (
            {
                DEVICE_CONNECTED_RECEIVED: MOCK_DEVICE_CONNECTED_EVENT,
                DEVICE_DISCONNECTED_RECEIVED: MOCK_DEVICE_DISCONNECTED_EVENT,
            }
        ),
        (
            {
                DEVICE_PAUSED_RECEIVED: MOCK_DEVICE_PAUSED_EVENT,
                DEVICE_DISCONNECTED_RECEIVED: MOCK_DEVICE_DISCONNECTED_EVENT,
            }
        ),
        (
            {
                DEVICE_PAUSED_RECEIVED: MOCK_DEVICE_PAUSED_EVENT,
                DEVICE_DISCONNECTED_RECEIVED: MOCK_DEVICE_DISCONNECTED_EVENT,
                DEVICE_RESUMED_RECEIVED: MOCK_DEVICE_RESUMED_EVENT,
            }
        ),
    ],
)
async def test_device_sensor_updates_on_event_sequence(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    events: dict[str, Any],
) -> None:
    """Test device sensor updates when receiving different events in a sequence."""
    for event_id, event in events.items():
        dispatcher.async_dispatcher_send(
            hass,
            f"{event_id}-{SERVER_ID}-{DEVICE_ID}",
            event,
        )
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


@pytest.mark.parametrize(
    ("event_id", "event"),
    [
        (FOLDER_SUMMARY_RECEIVED, MOCK_FOLDER_SUMMARY_EVENT),
        (STATE_CHANGED_RECEIVED, MOCK_STATE_CHANGED_EVENT),
        (FOLDER_PAUSED_RECEIVED, MOCK_FOLDER_PAUSED_EVENT),
    ],
)
async def test_folder_sensor_updates_on_event(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    event_id: str,
    event: dict[str, Any],
) -> None:
    """Test folder sensor updates when receiving different event."""
    dispatcher.async_dispatcher_send(
        hass,
        f"{event_id}-{SERVER_ID}-{FOLDER_ID}",
        event,
    )
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_sensor_unavailable_on_server_unavailable(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test folder and device sensors become unavailable when server is unavailable."""
    dispatcher.async_dispatcher_send(
        hass,
        f"{SERVER_UNAVAILABLE}-{SERVER_ID}",
    )
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_sensor_available_on_server_available(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test folder and device sensors become available when server comes back online."""
    dispatcher.async_dispatcher_send(
        hass,
        f"{SERVER_UNAVAILABLE}-{SERVER_ID}",
    )
    await hass.async_block_till_done()

    dispatcher.async_dispatcher_send(
        hass,
        f"{SERVER_AVAILABLE}-{SERVER_ID}",
    )
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_device_sensor_polls_status(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing: MagicMock,
) -> None:
    """Test device sensor polls for status updates."""
    initial_call_count = mock_syncthing.config.devices.call_count

    future = dt_util.utcnow() + timedelta(seconds=121)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    assert mock_syncthing.config.devices.call_count > initial_call_count


async def test_folder_sensor_polls_status(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing: MagicMock,
) -> None:
    """Test folder sensor polls for status updates."""
    syncing_status = {**MOCK_FOLDER_STATUS, "state": "syncing"}
    mock_syncthing.database.status = AsyncMock(return_value=syncing_status)

    future = dt_util.utcnow() + timedelta(seconds=121)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get(FOLDER_ENTITY_ID)
    assert state is not None and state.state == "syncing"


async def test_sensor_poll_error_makes_unavailable(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test folder and device sensors become unavailable on status error."""
    mock_syncthing.database.status = AsyncMock(side_effect=SyncthingError("Error"))
    mock_syncthing.config.devices = AsyncMock(side_effect=SyncthingError("Error"))

    future = dt_util.utcnow() + timedelta(seconds=121)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
