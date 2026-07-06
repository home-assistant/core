"""Tests for the syncthing sensor platform."""

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from aiosyncthing.exceptions import SyncthingError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.syncthing.const import (
    DEVICE_EVENTS,
    DOMAIN,
    FOLDER_EVENTS,
    SCAN_INTERVAL,
    SERVER_AVAILABLE,
    SERVER_UNAVAILABLE,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import dispatcher, entity_registry as er
from homeassistant.util import dt as dt_util

from . import DEVICE_ID, FOLDER_ID, SERVER_ID, SERVER_ID_SHORT_HA

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    load_json_object_fixture,
    snapshot_platform,
)


async def test_sensor_platform_setup(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_syncthing: MagicMock,
) -> None:
    """Test sensor platform sets up folder sensors."""
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_sensor_platform_no_sensors_on_config_error(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_syncthing_client: MagicMock,
) -> None:
    """Test sensor platform does not create folder sensors when config fetch fails."""
    mock_syncthing_client.config.config.side_effect = SyncthingError("Connection error")

    with patch(
        "homeassistant.components.syncthing.aiosyncthing.Syncthing",
        autospec=True,
    ) as mock_class:
        mock_class.return_value = mock_syncthing_client
        await hass.config_entries.async_setup(entry.entry_id)

        assert entry.state is ConfigEntryState.LOADED
        entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{SERVER_ID_SHORT_HA}-{FOLDER_ID}"
        )
        assert entity_id is None


@pytest.mark.parametrize(
    "event_fixture",
    [
        "folder_summary_event.json",
        "state_changed_event.json",
        "folder_paused_event.json",
    ],
)
async def test_folder_sensor_updates_on_event(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    event_fixture: str,
) -> None:
    """Test folder sensor updates when receiving different events."""
    event = await hass.async_add_executor_job(
        load_json_object_fixture, event_fixture, DOMAIN
    )

    folder = event["data"].get("folder") or event["data"]["id"]
    signal = f"{FOLDER_EVENTS[event['type']]}-{SERVER_ID}-{folder}"

    dispatcher.async_dispatcher_send(hass, signal, event)
    await hass.async_block_till_done()
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


@pytest.mark.parametrize(
    ("unique_id_suffix", "initial_state"),
    [
        pytest.param(FOLDER_ID, "idle", id="folder"),
        pytest.param(DEVICE_ID, "unknown", id="device"),
    ],
)
async def test_sensor_unavailable_on_server_unavailable(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing: MagicMock,
    entity_registry: er.EntityRegistry,
    unique_id_suffix: str,
    initial_state: str,
) -> None:
    """Test sensor becomes unavailable when server is unavailable."""
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SERVER_ID_SHORT_HA}-{unique_id_suffix}"
    )
    state = hass.states.get(entity_id) if entity_id else None
    assert state is not None and state.state == initial_state

    dispatcher.async_dispatcher_send(
        hass,
        f"{SERVER_UNAVAILABLE}-{SERVER_ID}",
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id) if entity_id else None
    assert state is not None and state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("unique_id_suffix", "recovered_state"),
    [
        pytest.param(FOLDER_ID, "idle", id="folder"),
        pytest.param(DEVICE_ID, "unknown", id="device"),
    ],
)
async def test_sensor_available_on_server_available(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing: MagicMock,
    entity_registry: er.EntityRegistry,
    unique_id_suffix: str,
    recovered_state: str,
) -> None:
    """Test sensor becomes available when server comes back online."""
    dispatcher.async_dispatcher_send(
        hass,
        f"{SERVER_UNAVAILABLE}-{SERVER_ID}",
    )
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SERVER_ID_SHORT_HA}-{unique_id_suffix}"
    )
    state = hass.states.get(entity_id) if entity_id else None
    assert state is not None and state.state == STATE_UNAVAILABLE

    dispatcher.async_dispatcher_send(
        hass,
        f"{SERVER_AVAILABLE}-{SERVER_ID}",
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id) if entity_id else None
    assert state is not None and state.state == recovered_state


async def test_folder_sensor_polls_status(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test folder sensor polls for status updates."""
    syncing_status = await hass.async_add_executor_job(
        load_json_object_fixture, "folder_status.json", DOMAIN
    )
    syncing_status["state"] = "syncing"
    mock_syncthing.database.status = AsyncMock(return_value=syncing_status)

    future = dt_util.utcnow() + SCAN_INTERVAL + timedelta(seconds=1)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SERVER_ID_SHORT_HA}-{FOLDER_ID}"
    )
    state = hass.states.get(entity_id) if entity_id else None
    assert state is not None and state.state == "syncing"


async def test_folder_sensor_error_makes_unavailable(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test folder sensor becomes unavailable on status error."""
    mock_syncthing.database.status = AsyncMock(side_effect=SyncthingError("Error"))

    future = dt_util.utcnow() + SCAN_INTERVAL + timedelta(seconds=1)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SERVER_ID_SHORT_HA}-{FOLDER_ID}"
    )
    state = hass.states.get(entity_id) if entity_id else None
    assert state is not None and state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    "event_fixture",
    [
        "device_connected_event.json",
        "device_disconnected_event.json",
        "device_paused_event.json",
        "device_resumed_event.json",
    ],
)
async def test_device_sensor_updates_on_event(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    event_fixture: str,
) -> None:
    """Test device sensor updates when receiving different events."""
    event = await hass.async_add_executor_job(
        load_json_object_fixture, event_fixture, DOMAIN
    )

    device = event["data"].get("device") or event["data"]["id"]
    signal = f"{DEVICE_EVENTS[event['type']]}-{SERVER_ID}-{device}"

    dispatcher.async_dispatcher_send(hass, signal, event)
    await hass.async_block_till_done()
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_device_sensor_polls_status(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test device sensor polls for config updates."""
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SERVER_ID_SHORT_HA}-{DEVICE_ID}"
    )
    initial = hass.states.get(entity_id) if entity_id else None
    assert initial is not None and initial.attributes["paused"] is False

    device_config = await hass.async_add_executor_job(
        load_json_object_fixture, "device_config.json", DOMAIN
    )
    device_config["paused"] = True
    mock_syncthing.config.devices = AsyncMock(return_value=device_config)

    future = dt_util.utcnow() + SCAN_INTERVAL + timedelta(seconds=1)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id) if entity_id else None
    assert state is not None and state.attributes["paused"] is True


async def test_device_sensor_error_makes_unavailable(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test device sensor becomes unavailable on status error."""
    mock_syncthing.config.devices = AsyncMock(side_effect=SyncthingError("Error"))

    future = dt_util.utcnow() + SCAN_INTERVAL + timedelta(seconds=1)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SERVER_ID_SHORT_HA}-{DEVICE_ID}"
    )
    state = hass.states.get(entity_id) if entity_id else None
    assert state is not None and state.state == STATE_UNAVAILABLE


async def test_local_server_device_online(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the local server device is always shown as online."""
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SERVER_ID_SHORT_HA}-{SERVER_ID}"
    )
    state = hass.states.get(entity_id) if entity_id else None
    assert state is not None and state.state == "online"


@pytest.mark.parametrize(
    ("event_fixture", "expected_state"),
    [
        pytest.param("device_connected_event.json", "connected", id="connected"),
        pytest.param(
            "device_disconnected_event.json", "disconnected", id="disconnected"
        ),
        pytest.param("device_paused_event.json", "paused", id="paused"),
        pytest.param("device_resumed_event.json", "disconnected", id="resumed"),
    ],
)
async def test_device_sensor_initial_events_ready(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing_client: MagicMock,
    entity_registry: er.EntityRegistry,
    event_fixture: str,
    expected_state: str,
) -> None:
    """Test device sensor reflects the last device event from initial events on startup."""
    initial_event = await hass.async_add_executor_job(
        load_json_object_fixture, event_fixture, DOMAIN
    )
    trigger_event = await hass.async_add_executor_job(
        load_json_object_fixture, "ping_event.json", DOMAIN
    )
    ready_to_trigger = asyncio.Event()

    async def mock_listen():
        yield initial_event
        await ready_to_trigger.wait()
        mock_syncthing_client.events.last_seen_id = 10
        yield trigger_event
        await asyncio.Event().wait()

    mock_syncthing_client.events.last_seen_id = 0
    mock_syncthing_client.events.listen = mock_listen
    with patch(
        "homeassistant.components.syncthing.aiosyncthing.Syncthing",
        autospec=True,
    ) as mock_class:
        mock_class.return_value = mock_syncthing_client
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        ready_to_trigger.set()
        await hass.async_block_till_done()
        entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{SERVER_ID_SHORT_HA}-{DEVICE_ID}"
        )
        state = hass.states.get(entity_id) if entity_id else None
        assert state is not None and state.state == expected_state
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_device_sensor_direct_compute_after_events_ready(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entity added after INITIAL_EVENTS_READY derives state from the buffer."""
    connected_event = await hass.async_add_executor_job(
        load_json_object_fixture, "device_connected_event.json", DOMAIN
    )
    client = entry.runtime_data
    client._initial_events = [connected_event]
    client._initial_events_processed = True

    await hass.config_entries.async_unload_platforms(entry, [Platform.SENSOR])
    await hass.async_block_till_done()
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SERVER_ID_SHORT_HA}-{DEVICE_ID}"
    )
    state = hass.states.get(entity_id) if entity_id else None
    assert state is not None and state.state == "connected"
