"""Tests for the syncthing sensor platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from aiosyncthing.exceptions import SyncthingError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.syncthing.const import (
    FOLDER_PAUSED_RECEIVED,
    FOLDER_SUMMARY_RECEIVED,
    SERVER_AVAILABLE,
    SERVER_UNAVAILABLE,
    STATE_CHANGED_RECEIVED,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import dispatcher, entity_registry as er
from homeassistant.util import dt as dt_util

from . import (
    FOLDER_ENTITY_ID,
    FOLDER_ID,
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
    """Test sensor platform sets up folder sensors."""
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
    assert state is not None and state.state == STATE_UNAVAILABLE


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
    assert state is not None and state.state == STATE_UNAVAILABLE

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
    assert state is not None and state.state == STATE_UNAVAILABLE
