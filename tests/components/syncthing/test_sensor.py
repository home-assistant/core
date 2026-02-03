"""Tests for the syncthing sensor platform."""

from collections.abc import AsyncIterator
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from aiosyncthing.exceptions import SyncthingError
import pytest

from homeassistant.components.syncthing.const import (
    DOMAIN,
    FOLDER_PAUSED_RECEIVED,
    FOLDER_SUMMARY_RECEIVED,
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
    FOLDER_ENTITY_ID,
    FOLDER_ID,
    FOLDER_LABEL,
    MOCK_FOLDER_PAUSED_EVENT,
    MOCK_FOLDER_STATUS,
    MOCK_FOLDER_SUMMARY_EVENT,
    MOCK_STATE_CHANGED_EVENT,
    SERVER_ID,
    create_mock_syncthing_client,
)

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture
async def mock_syncthing(
    hass: HomeAssistant,
    entry: MockConfigEntry,
) -> AsyncIterator[MagicMock]:
    """Create a mock Syncthing client and set up the config entry."""
    mock_syncthing = create_mock_syncthing_client()
    with patch(
        "homeassistant.components.syncthing.aiosyncthing.Syncthing",
        return_value=mock_syncthing,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        yield mock_syncthing


@pytest.fixture
def entry(hass: HomeAssistant) -> MockConfigEntry:
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
    folder_state = hass.states.get(FOLDER_ENTITY_ID)
    assert folder_state is not None
    assert folder_state.state == "idle"
    assert folder_state.attributes["id"] == FOLDER_ID
    assert folder_state.attributes["label"] == FOLDER_LABEL


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
    state = hass.states.get(FOLDER_ENTITY_ID)
    assert state is not None and state.state == "idle"

    dispatcher.async_dispatcher_send(
        hass,
        f"{FOLDER_SUMMARY_RECEIVED}-{SERVER_ID}-{FOLDER_ID}",
        MOCK_FOLDER_SUMMARY_EVENT,
    )
    await hass.async_block_till_done()

    state = hass.states.get(FOLDER_ENTITY_ID)
    assert state is not None and state.state == "syncing"


async def test_folder_sensor_updates_on_state_changed_event(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing: MagicMock,
) -> None:
    """Test folder sensor updates when receiving StateChanged event."""
    dispatcher.async_dispatcher_send(
        hass,
        f"{STATE_CHANGED_RECEIVED}-{SERVER_ID}-{FOLDER_ID}",
        MOCK_STATE_CHANGED_EVENT,
    )
    await hass.async_block_till_done()

    state = hass.states.get(FOLDER_ENTITY_ID)
    assert state is not None and state.state == "syncing"


async def test_folder_sensor_updates_on_paused_event(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing: MagicMock,
) -> None:
    """Test folder sensor updates when receiving FolderPaused event."""
    dispatcher.async_dispatcher_send(
        hass,
        f"{FOLDER_PAUSED_RECEIVED}-{SERVER_ID}-{FOLDER_ID}",
        MOCK_FOLDER_PAUSED_EVENT,
    )
    await hass.async_block_till_done()

    state = hass.states.get(FOLDER_ENTITY_ID)
    assert state is not None and state.state == "paused"


async def test_folder_sensor_unavailable_on_server_unavailable(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing: MagicMock,
) -> None:
    """Test folder sensor becomes unavailable when server is unavailable."""
    state = hass.states.get(FOLDER_ENTITY_ID)
    assert state is not None and state.state == "idle"

    dispatcher.async_dispatcher_send(
        hass,
        f"{SERVER_UNAVAILABLE}-{SERVER_ID}",
    )
    await hass.async_block_till_done()

    state = hass.states.get(FOLDER_ENTITY_ID)
    assert state is not None and state.state == "unavailable"


async def test_folder_sensor_available_on_server_available(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing: MagicMock,
) -> None:
    """Test folder sensor becomes available when server comes back online."""
    dispatcher.async_dispatcher_send(
        hass,
        f"{SERVER_UNAVAILABLE}-{SERVER_ID}",
    )
    await hass.async_block_till_done()

    state = hass.states.get(FOLDER_ENTITY_ID)
    assert state is not None and state.state == "unavailable"

    dispatcher.async_dispatcher_send(
        hass,
        f"{SERVER_AVAILABLE}-{SERVER_ID}",
    )
    await hass.async_block_till_done()

    state = hass.states.get(FOLDER_ENTITY_ID)
    assert state is not None and state.state == "idle"


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


async def test_folder_sensor_error_makes_unavailable(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_syncthing: MagicMock,
) -> None:
    """Test folder sensor becomes unavailable on status error."""
    mock_syncthing.database.status = AsyncMock(side_effect=SyncthingError("Error"))

    future = dt_util.utcnow() + timedelta(seconds=121)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get(FOLDER_ENTITY_ID)
    assert state is not None and state.state == "unavailable"
