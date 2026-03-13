"""Tests for the UniFi Access coordinator."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from unifi_access_api import (
    ApiAuthError,
    ApiConnectionError,
    ApiError,
    DoorLockRelayStatus,
)
from unifi_access_api.models.websocket import (
    LocationUpdateData,
    LocationUpdateState,
    LocationUpdateV2,
    V2LocationState,
    V2LocationUpdate,
    V2LocationUpdateData,
)

from homeassistant.components.lock import LockState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def _make_location_update(
    door_id: str = "door-001",
    lock: str = "unlocked",
    *,
    state: LocationUpdateState | None = None,
) -> LocationUpdateV2:
    """Create a LocationUpdateV2 message for testing."""
    return LocationUpdateV2(
        event="access.data.device.location_update_v2",
        data=LocationUpdateData(
            id=door_id,
            location_type="door",
            state=state if state is not None else LocationUpdateState(lock=lock),
        ),
    )


async def test_update_data_auth_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test coordinator handles auth error as update failure."""
    mock_client.get_doors.side_effect = ApiAuthError()

    coordinator = init_integration.runtime_data
    await coordinator.async_refresh()

    assert coordinator.last_update_success is False


async def test_update_data_api_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test coordinator handles API error as update failure."""
    mock_client.get_doors.side_effect = ApiError("API error")

    coordinator = init_integration.runtime_data
    await coordinator.async_refresh()

    assert coordinator.last_update_success is False


async def test_update_data_connection_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test coordinator handles connection error as update failure."""
    mock_client.get_doors.side_effect = ApiConnectionError("Connection failed")

    coordinator = init_integration.runtime_data
    await coordinator.async_refresh()

    assert coordinator.last_update_success is False


async def test_ws_disconnect_marks_unavailable(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test WebSocket disconnect marks coordinator as having an update error."""
    coordinator = init_integration.runtime_data
    assert coordinator.last_update_success is True

    coordinator._on_ws_disconnect()

    assert coordinator.last_update_success is False


async def test_ws_connect_triggers_refresh(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test WebSocket connect triggers a data refresh to recover availability."""
    coordinator = init_integration.runtime_data

    # Simulate disconnect → unavailable
    coordinator._on_ws_disconnect()
    assert coordinator.last_update_success is False

    # Simulate reconnect
    coordinator._on_ws_connect()
    await hass.async_block_till_done()

    # Refresh should have been triggered, restoring availability
    assert coordinator.last_update_success is True
    assert mock_client.get_doors.call_count == 2


async def test_ws_connect_no_refresh_when_healthy(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test initial WebSocket connect does not trigger redundant refresh."""
    coordinator = init_integration.runtime_data
    assert coordinator.last_update_success is True

    coordinator._on_ws_connect()
    await hass.async_block_till_done()

    # No extra refresh — only the initial setup call
    assert mock_client.get_doors.call_count == 1


@pytest.mark.parametrize(
    ("handler_method", "message"),
    [
        (
            "_handle_location_update",
            LocationUpdateV2(
                event="access.data.device.location_update_v2",
                data=LocationUpdateData(
                    id="door-001",
                    location_type="door",
                    state=LocationUpdateState(lock="unlocked"),
                ),
            ),
        ),
        (
            "_handle_v2_location_update",
            V2LocationUpdate(
                event="access.data.v2.location.update",
                data=V2LocationUpdateData(
                    id="door-001",
                    state=V2LocationState(lock="unlocked"),
                ),
            ),
        ),
    ],
)
async def test_handle_ws_update_unlock(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    handler_method: str,
    message: LocationUpdateV2 | V2LocationUpdate,
) -> None:
    """Test WebSocket message updates door to unlocked."""
    coordinator = init_integration.runtime_data

    await getattr(coordinator, handler_method)(message)

    assert (
        coordinator.data["door-001"].door_lock_relay_status
        == DoorLockRelayStatus.UNLOCK
    )

    state = hass.states.get("lock.front_door")
    assert state is not None
    assert state.state == LockState.UNLOCKED


async def test_process_door_update_unknown_door(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test WebSocket update for unknown door is ignored."""
    coordinator = init_integration.runtime_data

    await coordinator._handle_location_update(
        _make_location_update(door_id="unknown-door")
    )

    assert "unknown-door" not in coordinator.data


async def test_process_door_update_none_state(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test WebSocket update with None state is ignored."""
    coordinator = init_integration.runtime_data

    msg = LocationUpdateV2(
        event="access.data.device.location_update_v2",
        data=LocationUpdateData(
            id="door-001",
            location_type="door",
            state=None,
        ),
    )
    await coordinator._handle_location_update(msg)

    # Door should remain unchanged (locked)
    assert (
        coordinator.data["door-001"].door_lock_relay_status == DoorLockRelayStatus.LOCK
    )


async def test_process_door_update_locked_state(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test WebSocket update with locked state sets lock relay to lock."""
    coordinator = init_integration.runtime_data

    # First unlock door-001 via a WS update
    await coordinator._handle_location_update(_make_location_update())
    assert (
        coordinator.data["door-001"].door_lock_relay_status
        == DoorLockRelayStatus.UNLOCK
    )

    # Now lock it again
    await coordinator._handle_location_update(_make_location_update(lock="locked"))
    assert (
        coordinator.data["door-001"].door_lock_relay_status == DoorLockRelayStatus.LOCK
    )
