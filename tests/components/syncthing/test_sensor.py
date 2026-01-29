"""Tests for the syncthing sensor platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from aiosyncthing.exceptions import SyncthingError
import pytest

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
from homeassistant.const import CONF_TOKEN, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import dispatcher
from homeassistant.util import dt as dt_util

from . import (
    DEVICE_ENTITY_ID,
    DEVICE_ID,
    DEVICE_NAME,
    FOLDER_ENTITY_ID,
    FOLDER_ID,
    FOLDER_LABEL,
    MOCK_DEVICE_CONNECTED_EVENT,
    MOCK_DEVICE_DISCONNECTED_EVENT,
    MOCK_DEVICE_PAUSED_EVENT,
    MOCK_DEVICE_RESUMED_EVENT,
    MOCK_FOLDER_PAUSED_EVENT,
    MOCK_FOLDER_STATUS,
    MOCK_FOLDER_SUMMARY_EVENT,
    MOCK_STATE_CHANGED_EVENT,
    SERVER_ENTITY_ID,
    SERVER_ID,
    create_mock_syncthing_client,
)

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture
def mock_syncthing():
    """Create a mock Syncthing client."""
    return create_mock_syncthing_client()


@pytest.fixture
def entry(hass: HomeAssistant):
    """Create a mock ConfigEntry for Syncthing component."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_URL: "http://127.0.0.1:8384",
            CONF_TOKEN: "test-token",
            CONF_VERIFY_SSL: True,
        },
    )
    entry.add_to_hass(hass)
    return entry


async def test_sensor_platform_setup(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing: MagicMock,
) -> None:
    """Test sensor platform sets up folder and device sensors."""
    with patch(
        "homeassistant.components.syncthing.aiosyncthing.Syncthing",
        return_value=mock_syncthing,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Check folder sensor
    folder_state = hass.states.get(FOLDER_ENTITY_ID)
    assert folder_state is not None
    assert folder_state.state == "idle"
    assert folder_state.attributes["id"] == FOLDER_ID
    assert folder_state.attributes["label"] == FOLDER_LABEL

    # Check device sensor
    device_state = hass.states.get(DEVICE_ENTITY_ID)
    assert device_state is not None
    assert device_state.state == "unknown"

    # Check server device sensor (should be online)
    server_state = hass.states.get(SERVER_ENTITY_ID)
    assert server_state is not None
    assert server_state.state == "online"


async def test_sensor_platform_setup_fails_on_error(
    hass: HomeAssistant,
    entry: MockConfigEntry,
) -> None:
    """Test sensor platform setup fails when cannot get config."""
    mock_client = create_mock_syncthing_client(raise_connection_error=True)

    with patch(
        "homeassistant.components.syncthing.aiosyncthing.Syncthing",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_folder_sensor_updates_on_summary_event(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing: MagicMock,
) -> None:
    """Test folder sensor updates when receiving FolderSummary event."""
    with patch(
        "homeassistant.components.syncthing.aiosyncthing.Syncthing",
        return_value=mock_syncthing,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Initial state
    state = hass.states.get(FOLDER_ENTITY_ID)
    assert state.state == "idle"

    # Dispatch FolderSummary event
    dispatcher.async_dispatcher_send(
        hass,
        f"{FOLDER_SUMMARY_RECEIVED}-{SERVER_ID}-{FOLDER_ID}",
        MOCK_FOLDER_SUMMARY_EVENT,
    )
    await hass.async_block_till_done()

    # State should be updated
    state = hass.states.get(FOLDER_ENTITY_ID)
    assert state.state == "syncing"


async def test_folder_sensor_updates_on_state_changed_event(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing: MagicMock,
) -> None:
    """Test folder sensor updates when receiving StateChanged event."""
    with patch(
        "homeassistant.components.syncthing.aiosyncthing.Syncthing",
        return_value=mock_syncthing,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Dispatch StateChanged event
    dispatcher.async_dispatcher_send(
        hass,
        f"{STATE_CHANGED_RECEIVED}-{SERVER_ID}-{FOLDER_ID}",
        MOCK_STATE_CHANGED_EVENT,
    )
    await hass.async_block_till_done()

    # State should be updated
    state = hass.states.get(FOLDER_ENTITY_ID)
    assert state.state == "syncing"


async def test_folder_sensor_updates_on_paused_event(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing: MagicMock,
) -> None:
    """Test folder sensor updates when receiving FolderPaused event."""
    with patch(
        "homeassistant.components.syncthing.aiosyncthing.Syncthing",
        return_value=mock_syncthing,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Dispatch FolderPaused event
    dispatcher.async_dispatcher_send(
        hass,
        f"{FOLDER_PAUSED_RECEIVED}-{SERVER_ID}-{FOLDER_ID}",
        MOCK_FOLDER_PAUSED_EVENT,
    )
    await hass.async_block_till_done()

    # State should be paused
    state = hass.states.get(FOLDER_ENTITY_ID)
    assert state.state == "paused"


async def test_folder_sensor_unavailable_on_server_unavailable(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing: MagicMock,
) -> None:
    """Test folder sensor becomes unavailable when server is unavailable."""
    with patch(
        "homeassistant.components.syncthing.aiosyncthing.Syncthing",
        return_value=mock_syncthing,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Initial state should be available
    state = hass.states.get(FOLDER_ENTITY_ID)
    assert state.state == "idle"

    # Dispatch server unavailable event
    dispatcher.async_dispatcher_send(
        hass,
        f"{SERVER_UNAVAILABLE}-{SERVER_ID}",
    )
    await hass.async_block_till_done()

    # State should be unavailable
    state = hass.states.get(FOLDER_ENTITY_ID)
    assert state.state == "unavailable"


async def test_folder_sensor_available_on_server_available(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing: MagicMock,
) -> None:
    """Test folder sensor becomes available when server comes back online."""
    with patch(
        "homeassistant.components.syncthing.aiosyncthing.Syncthing",
        return_value=mock_syncthing,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Make sensor unavailable
    dispatcher.async_dispatcher_send(
        hass,
        f"{SERVER_UNAVAILABLE}-{SERVER_ID}",
    )
    await hass.async_block_till_done()

    state = hass.states.get(FOLDER_ENTITY_ID)
    assert state.state == "unavailable"

    # Dispatch server available event
    dispatcher.async_dispatcher_send(
        hass,
        f"{SERVER_AVAILABLE}-{SERVER_ID}",
    )
    await hass.async_block_till_done()

    # State should be available again
    state = hass.states.get(FOLDER_ENTITY_ID)
    assert state.state == "idle"


async def test_folder_sensor_polls_status(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing: MagicMock,
) -> None:
    """Test folder sensor polls for status updates."""
    with patch(
        "homeassistant.components.syncthing.aiosyncthing.Syncthing",
        return_value=mock_syncthing,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Update mock to return syncing status
    syncing_status = {**MOCK_FOLDER_STATUS, "state": "syncing"}
    mock_syncthing.database.status = AsyncMock(return_value=syncing_status)

    # Trigger time change to force update
    future = dt_util.utcnow() + timedelta(seconds=121)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    # State should be updated
    state = hass.states.get(FOLDER_ENTITY_ID)
    assert state.state == "syncing"


async def test_folder_sensor_error_makes_unavailable(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing: MagicMock,
) -> None:
    """Test folder sensor becomes unavailable on status error."""
    with patch(
        "homeassistant.components.syncthing.aiosyncthing.Syncthing",
        return_value=mock_syncthing,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Make status raise error
    mock_syncthing.database.status = AsyncMock(side_effect=SyncthingError("Error"))

    # Trigger time change to force update
    future = dt_util.utcnow() + timedelta(seconds=121)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    # State should be unavailable
    state = hass.states.get(FOLDER_ENTITY_ID)
    assert state.state == "unavailable"


async def test_device_sensor_updates_on_connected_event(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing: MagicMock,
) -> None:
    """Test device sensor updates when receiving DeviceConnected event."""
    with patch(
        "homeassistant.components.syncthing.aiosyncthing.Syncthing",
        return_value=mock_syncthing,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Initial state
    state = hass.states.get(DEVICE_ENTITY_ID)
    assert state.state == "unknown"

    # Dispatch DeviceConnected event
    dispatcher.async_dispatcher_send(
        hass,
        f"{DEVICE_CONNECTED_RECEIVED}-{SERVER_ID}-{DEVICE_ID}",
        MOCK_DEVICE_CONNECTED_EVENT,
    )
    await hass.async_block_till_done()

    # State should be connected
    state = hass.states.get(DEVICE_ENTITY_ID)
    assert state.state == "connected"
    assert state.attributes["addr"] == "192.168.1.100:22000"
    assert state.attributes["name"] == DEVICE_NAME


async def test_device_sensor_updates_on_disconnected_event(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing: MagicMock,
) -> None:
    """Test device sensor updates when receiving DeviceDisconnected event."""
    with patch(
        "homeassistant.components.syncthing.aiosyncthing.Syncthing",
        return_value=mock_syncthing,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # First connect the device
    dispatcher.async_dispatcher_send(
        hass,
        f"{DEVICE_CONNECTED_RECEIVED}-{SERVER_ID}-{DEVICE_ID}",
        MOCK_DEVICE_CONNECTED_EVENT,
    )
    await hass.async_block_till_done()

    state = hass.states.get(DEVICE_ENTITY_ID)
    assert state.state == "connected"

    # Dispatch DeviceDisconnected event
    dispatcher.async_dispatcher_send(
        hass,
        f"{DEVICE_DISCONNECTED_RECEIVED}-{SERVER_ID}-{DEVICE_ID}",
        MOCK_DEVICE_DISCONNECTED_EVENT,
    )
    await hass.async_block_till_done()

    # State should be disconnected
    state = hass.states.get(DEVICE_ENTITY_ID)
    assert state.state == "disconnected"


async def test_device_sensor_updates_on_paused_event(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing: MagicMock,
) -> None:
    """Test device sensor updates when receiving DevicePaused event."""
    with patch(
        "homeassistant.components.syncthing.aiosyncthing.Syncthing",
        return_value=mock_syncthing,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Dispatch DevicePaused event
    dispatcher.async_dispatcher_send(
        hass,
        f"{DEVICE_PAUSED_RECEIVED}-{SERVER_ID}-{DEVICE_ID}",
        MOCK_DEVICE_PAUSED_EVENT,
    )
    await hass.async_block_till_done()

    # State should be paused
    state = hass.states.get(DEVICE_ENTITY_ID)
    assert state.state == "paused"


async def test_device_sensor_stays_paused_on_disconnect(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing: MagicMock,
) -> None:
    """Test device sensor stays paused when disconnected while paused."""
    with patch(
        "homeassistant.components.syncthing.aiosyncthing.Syncthing",
        return_value=mock_syncthing,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Pause device first
    dispatcher.async_dispatcher_send(
        hass,
        f"{DEVICE_PAUSED_RECEIVED}-{SERVER_ID}-{DEVICE_ID}",
        MOCK_DEVICE_PAUSED_EVENT,
    )
    await hass.async_block_till_done()

    # Dispatch DeviceDisconnected event
    dispatcher.async_dispatcher_send(
        hass,
        f"{DEVICE_DISCONNECTED_RECEIVED}-{SERVER_ID}-{DEVICE_ID}",
        MOCK_DEVICE_DISCONNECTED_EVENT,
    )
    await hass.async_block_till_done()

    # State should still be paused
    state = hass.states.get(DEVICE_ENTITY_ID)
    assert state.state == "paused"


async def test_device_sensor_updates_on_resumed_event(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing: MagicMock,
) -> None:
    """Test device sensor updates when receiving DeviceResumed event."""
    with patch(
        "homeassistant.components.syncthing.aiosyncthing.Syncthing",
        return_value=mock_syncthing,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Pause device first
    dispatcher.async_dispatcher_send(
        hass,
        f"{DEVICE_PAUSED_RECEIVED}-{SERVER_ID}-{DEVICE_ID}",
        MOCK_DEVICE_PAUSED_EVENT,
    )
    await hass.async_block_till_done()

    state = hass.states.get(DEVICE_ENTITY_ID)
    assert state.state == "paused"

    # Dispatch DeviceResumed event
    dispatcher.async_dispatcher_send(
        hass,
        f"{DEVICE_RESUMED_RECEIVED}-{SERVER_ID}-{DEVICE_ID}",
        MOCK_DEVICE_RESUMED_EVENT,
    )
    await hass.async_block_till_done()

    # State should be disconnected
    state = hass.states.get(DEVICE_ENTITY_ID)
    assert state.state == "disconnected"


async def test_device_sensor_processes_initial_events(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing: MagicMock,
) -> None:
    """Test device sensor processes initial events on startup."""
    with patch(
        "homeassistant.components.syncthing.aiosyncthing.Syncthing",
        return_value=mock_syncthing,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Get the syncthing client and add initial events
    syncthing = hass.data[DOMAIN][entry.entry_id]
    syncthing._initial_events = [
        MOCK_DEVICE_CONNECTED_EVENT,
        MOCK_DEVICE_PAUSED_EVENT,
        MOCK_DEVICE_DISCONNECTED_EVENT,
        MOCK_DEVICE_RESUMED_EVENT,
        MOCK_DEVICE_CONNECTED_EVENT,
        MOCK_DEVICE_DISCONNECTED_EVENT,
    ]

    # Dispatch initial events ready signal
    dispatcher.async_dispatcher_send(
        hass,
        f"{INITIAL_EVENTS_READY}-{SERVER_ID}",
    )
    await hass.async_block_till_done()

    # State should reflect the last event (disconnected)
    state = hass.states.get(DEVICE_ENTITY_ID)
    assert state.state == "disconnected"


async def test_device_sensor_unavailable_on_server_unavailable(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing: MagicMock,
) -> None:
    """Test device sensor becomes unavailable when server is unavailable."""
    with patch(
        "homeassistant.components.syncthing.aiosyncthing.Syncthing",
        return_value=mock_syncthing,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Initial state should be available
    state = hass.states.get(DEVICE_ENTITY_ID)
    assert state.state == "unknown"

    # Dispatch server unavailable event
    dispatcher.async_dispatcher_send(
        hass,
        f"{SERVER_UNAVAILABLE}-{SERVER_ID}",
    )
    await hass.async_block_till_done()

    # State should be unavailable
    state = hass.states.get(DEVICE_ENTITY_ID)
    assert state.state == "unavailable"


async def test_device_sensor_available_on_server_available(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing: MagicMock,
) -> None:
    """Test device sensor becomes available when server comes back online."""
    with patch(
        "homeassistant.components.syncthing.aiosyncthing.Syncthing",
        return_value=mock_syncthing,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Make sensor unavailable
    dispatcher.async_dispatcher_send(
        hass,
        f"{SERVER_UNAVAILABLE}-{SERVER_ID}",
    )
    await hass.async_block_till_done()

    state = hass.states.get(DEVICE_ENTITY_ID)
    assert state.state == "unavailable"

    # Dispatch server available event
    dispatcher.async_dispatcher_send(
        hass,
        f"{SERVER_AVAILABLE}-{SERVER_ID}",
    )
    await hass.async_block_till_done()

    # State should be available again
    state = hass.states.get(DEVICE_ENTITY_ID)
    assert state.state == "unknown"


async def test_device_sensor_polls_status(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing: MagicMock,
) -> None:
    """Test device sensor polls for status updates."""
    with patch(
        "homeassistant.components.syncthing.aiosyncthing.Syncthing",
        return_value=mock_syncthing,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Verify initial state
    initial_call_count = mock_syncthing.config.devices.call_count

    # Trigger time change to force update
    future = dt_util.utcnow() + timedelta(seconds=121)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    # Verify devices was called again
    assert mock_syncthing.config.devices.call_count > initial_call_count


async def test_device_sensor_error_makes_unavailable(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing: MagicMock,
) -> None:
    """Test device sensor becomes unavailable on config error."""
    with patch(
        "homeassistant.components.syncthing.aiosyncthing.Syncthing",
        return_value=mock_syncthing,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Make devices raise error
    mock_syncthing.config.devices = AsyncMock(side_effect=SyncthingError("Error"))

    # Trigger time change to force update
    future = dt_util.utcnow() + timedelta(seconds=121)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    # State should be unavailable
    state = hass.states.get(DEVICE_ENTITY_ID)
    assert state.state == "unavailable"
