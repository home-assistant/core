"""Tests for the UniFi Access integration setup."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from unittest.mock import MagicMock

import pytest
from unifi_access_api import (
    ApiAuthError,
    ApiConnectionError,
    ApiError,
    DoorPositionStatus,
)
from unifi_access_api.models.websocket import (
    LocationUpdateData,
    LocationUpdateState,
    LocationUpdateV2,
    SettingUpdate,
    SettingUpdateData,
    ThumbnailInfo,
    V2LocationState,
    V2LocationUpdate,
    V2LocationUpdateData,
    WebsocketMessage,
)

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


def _get_ws_handlers(
    mock_client: MagicMock,
) -> dict[str, Callable[[WebsocketMessage], Awaitable[None]]]:
    """Extract WebSocket handlers from mock client."""
    return mock_client.start_websocket.call_args[0][0]


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test successful setup of a config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_client.authenticate.assert_awaited_once()
    mock_client.get_doors.assert_awaited_once()


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        (ApiAuthError(), ConfigEntryState.SETUP_RETRY),
        (ApiConnectionError("Connection failed"), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_entry_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup handles errors correctly."""
    mock_client.authenticate.side_effect = exception
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state


@pytest.mark.parametrize(
    ("failing_method", "exception"),
    [
        ("get_doors", ApiAuthError()),
        ("get_doors", ApiConnectionError("Connection failed")),
        ("get_doors", ApiError("API error")),
        ("get_emergency_status", ApiAuthError()),
        ("get_emergency_status", ApiConnectionError("Connection failed")),
        ("get_emergency_status", ApiError("API error")),
    ],
)
async def test_coordinator_update_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    failing_method: str,
    exception: Exception,
) -> None:
    """Test coordinator handles update errors from get_doors or get_emergency_status."""
    getattr(mock_client, failing_method).side_effect = exception
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test unloading a config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_ws_location_update_v2(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test location_update_v2 WebSocket message updates door state."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    assert coordinator.data.doors["door-001"].door_lock_relay_status == "lock"

    handlers = _get_ws_handlers(mock_client)
    msg = LocationUpdateV2(
        event="access.data.device.location_update_v2",
        data=LocationUpdateData(
            id="door-001",
            location_type="DOOR",
            state=LocationUpdateState(
                dps=DoorPositionStatus.OPEN,
                lock="unlocked",
            ),
        ),
    )

    await handlers["access.data.device.location_update_v2"](msg)
    await hass.async_block_till_done()

    door = coordinator.data.doors["door-001"]
    assert door.door_position_status == "open"
    assert door.door_lock_relay_status == "unlock"


async def test_ws_v2_location_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test V2 location update WebSocket message updates door state."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    handlers = _get_ws_handlers(mock_client)
    msg = V2LocationUpdate(
        event="access.data.v2.location.update",
        data=V2LocationUpdateData(
            id="door-002",
            location_type="DOOR",
            name="Back Door",
            up_id="up-1",
            device_ids=[],
            state=V2LocationState(
                lock="locked",
                dps=DoorPositionStatus.CLOSE,
                dps_connected=True,
                is_unavailable=False,
            ),
        ),
    )

    await handlers["access.data.v2.location.update"](msg)
    await hass.async_block_till_done()

    door = coordinator.data.doors["door-002"]
    assert door.door_lock_relay_status == "lock"
    assert door.door_position_status == "close"


async def test_ws_location_update_unknown_door_ignored(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test location update for unknown door is silently ignored."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    original_data = coordinator.data

    handlers = _get_ws_handlers(mock_client)
    msg = LocationUpdateV2(
        event="access.data.device.location_update_v2",
        data=LocationUpdateData(
            id="door-unknown",
            location_type="DOOR",
            state=LocationUpdateState(
                dps=DoorPositionStatus.OPEN,
                lock="unlocked",
            ),
        ),
    )

    await handlers["access.data.device.location_update_v2"](msg)
    await hass.async_block_till_done()

    # Data should be unchanged
    assert coordinator.data is original_data


async def test_ws_location_update_no_state_ignored(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test location update with no state is silently ignored."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    original_data = coordinator.data

    handlers = _get_ws_handlers(mock_client)
    msg = LocationUpdateV2(
        event="access.data.device.location_update_v2",
        data=LocationUpdateData(
            id="door-001",
            location_type="DOOR",
            state=None,
        ),
    )

    await handlers["access.data.device.location_update_v2"](msg)
    await hass.async_block_till_done()

    assert coordinator.data is original_data


async def test_ws_location_update_with_thumbnail(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test location_update_v2 with thumbnail updates door_thumbnails."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    assert "door-002" not in coordinator.data.door_thumbnails

    handlers = _get_ws_handlers(mock_client)
    msg = LocationUpdateV2(
        event="access.data.device.location_update_v2",
        data=LocationUpdateData(
            id="door-002",
            location_type="DOOR",
            state=None,
            thumbnail=ThumbnailInfo(
                url="/thumb/door-002.jpg",
                door_thumbnail_last_update=1700000000,
            ),
        ),
    )

    await handlers["access.data.device.location_update_v2"](msg)
    await hass.async_block_till_done()

    assert "door-002" in coordinator.data.door_thumbnails
    thumb = coordinator.data.door_thumbnails["door-002"]
    assert thumb.url == "/thumb/door-002.jpg"
    assert thumb.door_thumbnail_last_update == 1700000000


async def test_coordinator_timeout_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test coordinator handles timeout from API."""
    mock_client.get_doors.side_effect = TimeoutError
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_ws_location_update_thumbnail_only_no_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test location update with thumbnail but no state keeps door unchanged."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    door_before = coordinator.data.doors["door-001"]

    handlers = _get_ws_handlers(mock_client)
    msg = LocationUpdateV2(
        event="access.data.device.location_update_v2",
        data=LocationUpdateData(
            id="door-001",
            location_type="DOOR",
            state=None,
            thumbnail=ThumbnailInfo(
                url="/thumb/door-001-new.jpg",
                door_thumbnail_last_update=1700002000,
            ),
        ),
    )

    await handlers["access.data.device.location_update_v2"](msg)
    await hass.async_block_till_done()

    # Door state unchanged, thumbnail updated
    assert coordinator.data.doors["door-001"] == door_before
    thumb = coordinator.data.door_thumbnails["door-001"]
    assert thumb.url == "/thumb/door-001-new.jpg"


async def test_ws_setting_update_before_data_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test setting update is ignored when coordinator has no data yet."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    # Force data to None to simulate pre-first-refresh state
    coordinator.data = None  # type: ignore[assignment]

    handlers = _get_ws_handlers(mock_client)
    msg = SettingUpdate(
        event="access.data.setting.update",
        data=SettingUpdateData(evacuation=True, lockdown=False),
    )

    await handlers["access.data.setting.update"](msg)
    await hass.async_block_till_done()

    assert coordinator.data is None
