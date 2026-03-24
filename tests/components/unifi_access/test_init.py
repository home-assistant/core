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
    ThumbnailInfo,
    V2LocationState,
    V2LocationUpdate,
    V2LocationUpdateData,
    WebsocketMessage,
)

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

FRONT_DOOR_BINARY_SENSOR = "binary_sensor.front_door"
BACK_DOOR_BINARY_SENSOR = "binary_sensor.back_door"
FRONT_DOOR_IMAGE = "image.front_door_thumbnail"
BACK_DOOR_IMAGE = "image.back_door_thumbnail"


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
        (ApiAuthError(), ConfigEntryState.SETUP_ERROR),
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

    if expected_state is ConfigEntryState.SETUP_ERROR:
        assert any(
            flow["context"]["source"] == SOURCE_REAUTH
            for flow in hass.config_entries.flow.async_progress()
        )


@pytest.mark.parametrize(
    ("failing_method", "exception", "expected_state"),
    [
        ("get_doors", ApiAuthError(), ConfigEntryState.SETUP_ERROR),
        (
            "get_doors",
            ApiConnectionError("Connection failed"),
            ConfigEntryState.SETUP_RETRY,
        ),
        ("get_doors", ApiError("API error"), ConfigEntryState.SETUP_RETRY),
        ("get_emergency_status", ApiAuthError(), ConfigEntryState.SETUP_ERROR),
        (
            "get_emergency_status",
            ApiConnectionError("Connection failed"),
            ConfigEntryState.SETUP_RETRY,
        ),
        ("get_emergency_status", ApiError("API error"), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_coordinator_update_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    failing_method: str,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test coordinator handles update errors from get_doors or get_emergency_status."""
    getattr(mock_client, failing_method).side_effect = exception
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state

    if expected_state is ConfigEntryState.SETUP_ERROR:
        assert any(
            flow["context"]["source"] == SOURCE_REAUTH
            for flow in hass.config_entries.flow.async_progress()
        )


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
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test location_update_v2 WebSocket message updates door state."""
    assert hass.states.get(FRONT_DOOR_BINARY_SENSOR).state == "off"

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

    assert hass.states.get(FRONT_DOOR_BINARY_SENSOR).state == "on"


async def test_ws_v2_location_update(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test V2 location update WebSocket message updates door state."""
    assert hass.states.get(BACK_DOOR_BINARY_SENSOR).state == "on"

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

    assert hass.states.get(BACK_DOOR_BINARY_SENSOR).state == "off"


async def test_ws_location_update_unknown_door_ignored(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test location update for unknown door is silently ignored."""
    state_before = hass.states.get(FRONT_DOOR_BINARY_SENSOR).state

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

    assert hass.states.get(FRONT_DOOR_BINARY_SENSOR).state == state_before


async def test_ws_location_update_no_state_ignored(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test location update with no state is silently ignored."""
    state_before = hass.states.get(FRONT_DOOR_BINARY_SENSOR).state

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

    assert hass.states.get(FRONT_DOOR_BINARY_SENSOR).state == state_before


async def test_ws_location_update_no_op_state_ignored(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test location update with state but no relevant fields is ignored."""
    state_before = hass.states.get(FRONT_DOOR_BINARY_SENSOR).state

    handlers = _get_ws_handlers(mock_client)
    msg = LocationUpdateV2(
        event="access.data.device.location_update_v2",
        data=LocationUpdateData(
            id="door-001",
            location_type="DOOR",
            state=LocationUpdateState.model_construct(
                dps=None,
                lock="unknown",
            ),
        ),
    )

    await handlers["access.data.device.location_update_v2"](msg)
    await hass.async_block_till_done()

    assert hass.states.get(FRONT_DOOR_BINARY_SENSOR).state == state_before


async def test_ws_location_update_with_thumbnail(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test location_update_v2 with thumbnail updates image entity."""
    assert hass.states.get(BACK_DOOR_IMAGE).state == "unknown"

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

    assert hass.states.get(BACK_DOOR_IMAGE).state != "unknown"


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
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test location update with thumbnail but no state keeps door unchanged."""
    state_before = hass.states.get(FRONT_DOOR_BINARY_SENSOR).state
    image_state_before = hass.states.get(FRONT_DOOR_IMAGE).state

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
    assert hass.states.get(FRONT_DOOR_BINARY_SENSOR).state == state_before
    assert hass.states.get(FRONT_DOOR_IMAGE).state != image_state_before
