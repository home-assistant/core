"""Tests for the Homecast coordinator."""

import copy
from unittest.mock import AsyncMock, patch

from pyhomecast import (
    HomecastAuthError,
    HomecastConnectionError,
    HomecastDevice,
    HomecastError,
    HomecastHome,
    HomecastState,
)
import pytest

from homeassistant.components.homecast.coordinator import HomecastCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from tests.common import MockConfigEntry


async def _setup_and_get_coordinator(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> HomecastCoordinator:
    """Set up the integration and return the coordinator."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    return mock_config_entry.runtime_data.coordinator


async def test_ws_characteristic_update(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test WebSocket characteristic_update applies state change."""
    coordinator = await _setup_and_get_coordinator(
        hass, mock_homecast, mock_config_entry
    )

    # Verify initial brightness
    device_key = "my_home_0bf8.living_room_a1b2.ceiling_light_c3d4"
    assert coordinator.data.devices[device_key].state["brightness"] == 80

    # Simulate a brightness update via WebSocket
    coordinator._on_ws_message(
        {
            "type": "characteristic_update",
            "homeId": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXX0BF8",
            "accessoryId": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXC3D4",
            "characteristicType": "brightness",
            "value": 50,
        }
    )

    assert coordinator.data.devices[device_key].state["brightness"] == 50


async def test_ws_characteristic_update_triggers_refresh_for_power(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that power-related characteristic updates apply state change."""
    coordinator = await _setup_and_get_coordinator(
        hass, mock_homecast, mock_config_entry
    )

    device_key = "my_home_0bf8.living_room_a1b2.ceiling_light_c3d4"
    assert coordinator.data.devices[device_key].state["on"] is True

    coordinator._on_ws_message(
        {
            "type": "characteristic_update",
            "homeId": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXX0BF8",
            "accessoryId": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXC3D4",
            "characteristicType": "on",
            "value": False,
        }
    )

    assert coordinator.data.devices[device_key].state["on"] is False


async def test_ws_service_group_update(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test WebSocket service_group_update triggers refresh."""
    coordinator = await _setup_and_get_coordinator(
        hass, mock_homecast, mock_config_entry
    )

    with patch.object(coordinator, "async_request_refresh") as mock_refresh:
        coordinator._on_ws_message(
            {
                "type": "service_group_update",
                "homeId": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXX0BF8",
                "groupId": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXC3D4",
                "characteristicType": "on",
                "value": True,
            }
        )
        mock_refresh.assert_called_once()


async def test_ws_reachability_update(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test WebSocket reachability_update triggers refresh."""
    coordinator = await _setup_and_get_coordinator(
        hass, mock_homecast, mock_config_entry
    )

    with patch.object(coordinator, "async_request_refresh") as mock_refresh:
        coordinator._on_ws_message({"type": "reachability_update"})
        mock_refresh.assert_called_once()


async def test_ws_relay_status_disconnected(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test WebSocket relay_status_update triggers refresh when disconnected."""
    coordinator = await _setup_and_get_coordinator(
        hass, mock_homecast, mock_config_entry
    )

    with patch.object(coordinator, "async_request_refresh") as mock_refresh:
        coordinator._on_ws_message({"type": "relay_status_update", "connected": False})
        mock_refresh.assert_called_once()


async def test_ws_relay_status_connected_no_refresh(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test WebSocket relay_status_update does NOT refresh when connected."""
    coordinator = await _setup_and_get_coordinator(
        hass, mock_homecast, mock_config_entry
    )

    with patch.object(coordinator, "async_request_refresh") as mock_refresh:
        coordinator._on_ws_message({"type": "relay_status_update", "connected": True})
        mock_refresh.assert_not_called()


async def test_ws_unknown_message_type(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test WebSocket ignores unknown message types."""
    coordinator = await _setup_and_get_coordinator(
        hass, mock_homecast, mock_config_entry
    )

    with patch.object(coordinator, "async_request_refresh") as mock_refresh:
        coordinator._on_ws_message({"type": "unknown_type"})
        mock_refresh.assert_not_called()


async def test_apply_state_update_unknown_device(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test _apply_state_update ignores unknown accessory IDs."""
    coordinator = await _setup_and_get_coordinator(
        hass, mock_homecast, mock_config_entry
    )

    # Should not raise — unknown device is silently ignored
    coordinator._on_ws_message(
        {
            "type": "characteristic_update",
            "homeId": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXFFFF",
            "accessoryId": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXFFFF",
            "characteristicType": "on",
            "value": True,
        }
    )


async def test_apply_state_update_unknown_char_type(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test _apply_state_update ignores unknown characteristic types."""
    coordinator = await _setup_and_get_coordinator(
        hass, mock_homecast, mock_config_entry
    )

    device_key = "my_home_0bf8.living_room_a1b2.ceiling_light_c3d4"
    original_state = dict(coordinator.data.devices[device_key].state)

    coordinator._on_ws_message(
        {
            "type": "characteristic_update",
            "homeId": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXX0BF8",
            "accessoryId": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXC3D4",
            "characteristicType": "unknown_characteristic",
            "value": 99,
        }
    )

    # State should be unchanged
    assert coordinator.data.devices[device_key].state == original_state


async def test_apply_state_update_missing_ids(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test _apply_state_update handles missing homeId/accessoryId."""
    coordinator = await _setup_and_get_coordinator(
        hass, mock_homecast, mock_config_entry
    )

    # Missing homeId
    coordinator._on_ws_message(
        {
            "type": "characteristic_update",
            "accessoryId": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXC3D4",
            "characteristicType": "on",
            "value": True,
        }
    )

    # Missing accessoryId
    coordinator._on_ws_message(
        {
            "type": "characteristic_update",
            "homeId": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXX0BF8",
            "characteristicType": "on",
            "value": True,
        }
    )


async def test_ws_setup_failure_falls_back_to_polling(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that WebSocket connection failure falls back to polling."""
    # Make the WS connect fail — the conftest already mocks HomecastWebSocket,
    # so we patch the coordinator's setup method to simulate WS failure
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homecast.coordinator.HomecastCoordinator.async_setup_websocket",
        new_callable=AsyncMock,
    ) as mock_ws_setup:
        # Simulate WS setup that doesn't reduce the polling interval
        mock_ws_setup.return_value = None

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    coordinator = mock_config_entry.runtime_data.coordinator
    # Polling interval should remain at the default (WS setup was mocked to no-op)
    assert coordinator.update_interval.total_seconds() == 30


async def test_ws_setup_connects_and_subscribes(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_setup_websocket connects, subscribes, and reduces polling."""
    coordinator = await _setup_and_get_coordinator(
        hass, mock_homecast, mock_config_entry
    )

    # The conftest mock auto-connects — verify polling was reduced
    assert coordinator.update_interval.total_seconds() == 300


async def test_uuid_mapping_resolves_devices(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test _build_uuid_mapping and _resolve_device_key."""
    coordinator = await _setup_and_get_coordinator(
        hass, mock_homecast, mock_config_entry
    )

    # "ceiling_light_c3d4" in home "my_home_0bf8"
    # UUID suffix matching: home[-4:]="0bf8", accessory[-4:]="c3d4"
    result = coordinator._resolve_device_key(
        "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXX0BF8",
        "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXC3D4",
    )
    assert result == "my_home_0bf8.living_room_a1b2.ceiling_light_c3d4"


async def test_async_shutdown_disconnects_ws(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_shutdown disconnects the WebSocket."""
    coordinator = await _setup_and_get_coordinator(
        hass, mock_homecast, mock_config_entry
    )

    await coordinator.async_shutdown()
    # The WS mock's disconnect should have been called
    assert coordinator._ws.disconnect.called


async def test_apply_state_update_sets_value(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test _apply_state_update writes to device state and notifies."""
    coordinator = await _setup_and_get_coordinator(
        hass, mock_homecast, mock_config_entry
    )

    device_key = "my_home_0bf8.living_room_a1b2.ceiling_light_c3d4"
    assert coordinator.data.devices[device_key].state["on"] is True

    coordinator._apply_state_update(
        "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXX0BF8",
        "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXC3D4",
        "on",
        False,
    )

    assert coordinator.data.devices[device_key].state["on"] is False


async def test_apply_state_update_returns_none_when_no_data(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test _apply_state_update returns None when self.data is None."""
    mock_config_entry.add_to_hass(hass)

    # Build the coordinator manually so we can call _apply_state_update
    # before data is loaded
    coordinator = HomecastCoordinator(
        hass,
        mock_config_entry,
        mock_homecast,
        refresh_token=AsyncMock(return_value="token"),
        ws=None,
        initial_token=None,
    )

    # data is None before first refresh
    assert coordinator.data is None

    result = coordinator._apply_state_update(
        "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXX0BF8",
        "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXC3D4",
        "on",
        True,
    )
    assert result is None


async def test_ws_setup_no_token_skips_connect(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_setup_websocket skips connect when _current_token is None."""
    mock_config_entry.add_to_hass(hass)

    # Create a WS mock directly (don't patch — conftest already patches the class)
    ws = AsyncMock()
    ws.connect = AsyncMock()
    ws.disconnect = AsyncMock()
    ws.subscribe = AsyncMock()
    ws.set_callback = lambda cb: None
    ws.set_token = lambda token: None
    ws.connected = True

    coordinator = HomecastCoordinator(
        hass,
        mock_config_entry,
        mock_homecast,
        refresh_token=AsyncMock(return_value="token"),
        ws=ws,
        initial_token=None,  # No token
    )

    # Load data so subscribe + uuid mapping can work
    coordinator.data = copy.deepcopy(await mock_homecast.get_state())

    await coordinator.async_setup_websocket()

    # connect should NOT have been called (no token)
    ws.connect.assert_not_called()
    # But subscribe should still be called since data has homes
    ws.subscribe.assert_called_once()


async def test_ws_setup_connect_failure_falls_back(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_setup_websocket falls back to polling on connection error."""
    mock_config_entry.add_to_hass(hass)

    ws = AsyncMock()
    ws.connect = AsyncMock(side_effect=HomecastConnectionError("connection refused"))
    ws.disconnect = AsyncMock()
    ws.subscribe = AsyncMock()
    ws.set_callback = lambda cb: None
    ws.set_token = lambda token: None
    ws.connected = False

    coordinator = HomecastCoordinator(
        hass,
        mock_config_entry,
        mock_homecast,
        refresh_token=AsyncMock(return_value="token"),
        ws=ws,
        initial_token="mock-token",
    )

    coordinator.data = copy.deepcopy(await mock_homecast.get_state())

    await coordinator.async_setup_websocket()

    # connect was called but raised — should return early
    ws.connect.assert_called_once_with("mock-token")
    # subscribe should NOT be called because connect failed
    ws.subscribe.assert_not_called()
    # Polling interval should remain at default (not reduced)
    assert coordinator.update_interval.total_seconds() == 30


async def test_ws_group_propagation(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test characteristic_update propagates to group when member_to_group is set."""
    # Create a state with a group and a member that maps to it
    group_state = HomecastState(
        devices={
            "my_home_0bf8.living_room_a1b2.ceiling_light_c3d4": HomecastDevice(
                unique_id="my_home_0bf8.living_room_a1b2.ceiling_light_c3d4",
                name="Ceiling Light",
                room_name="Living Room",
                home_key="my_home_0bf8",
                home_name="My Home",
                room_key="living_room_a1b2",
                accessory_key="ceiling_light_c3d4",
                device_type="light",
                state={"on": True, "brightness": 80},
                settable=["on", "brightness"],
            ),
            "my_home_0bf8.living_room_a1b2.light_group_ef01": HomecastDevice(
                unique_id="my_home_0bf8.living_room_a1b2.light_group_ef01",
                name="Light Group",
                room_name="Living Room",
                home_key="my_home_0bf8",
                home_name="My Home",
                room_key="living_room_a1b2",
                accessory_key="light_group_ef01",
                device_type="light",
                state={"on": True, "brightness": 80},
                settable=["on", "brightness"],
            ),
        },
        homes={
            "my_home_0bf8": HomecastHome(
                key="my_home_0bf8",
                name="My Home",
                home_id="EEBCDDC0-F66D-5BD2-8D0E-C28CEC3FB454",
            ),
        },
        member_to_group={
            # ceiling_light_c3d4 is a member of light_group_ef01
            "my_home_0bf8.living_room_a1b2.ceiling_light_c3d4": "my_home_0bf8.living_room_a1b2.light_group_ef01",
        },
    )

    mock_homecast.get_state = AsyncMock(
        side_effect=lambda **kw: copy.deepcopy(group_state)
    )

    coordinator = await _setup_and_get_coordinator(
        hass, mock_homecast, mock_config_entry
    )

    # Verify initial state
    group_key = "my_home_0bf8.living_room_a1b2.light_group_ef01"
    assert coordinator.data.devices[group_key].state["brightness"] == 80

    # Send a characteristic_update for the member device
    coordinator._on_ws_message(
        {
            "type": "characteristic_update",
            "homeId": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXX0BF8",
            "accessoryId": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXC3D4",
            "characteristicType": "brightness",
            "value": 50,
        }
    )

    # The member's state should be updated
    member_key = "my_home_0bf8.living_room_a1b2.ceiling_light_c3d4"
    assert coordinator.data.devices[member_key].state["brightness"] == 50

    # The group's state should also be propagated
    assert coordinator.data.devices[group_key].state["brightness"] == 50


async def test_ws_group_propagation_unknown_char_type(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test group propagation is skipped for unknown characteristic types."""
    group_state = HomecastState(
        devices={
            "my_home_0bf8.living_room_a1b2.ceiling_light_c3d4": HomecastDevice(
                unique_id="my_home_0bf8.living_room_a1b2.ceiling_light_c3d4",
                name="Ceiling Light",
                room_name="Living Room",
                home_key="my_home_0bf8",
                home_name="My Home",
                room_key="living_room_a1b2",
                accessory_key="ceiling_light_c3d4",
                device_type="light",
                state={"on": True, "brightness": 80},
                settable=["on", "brightness"],
            ),
            "my_home_0bf8.living_room_a1b2.light_group_ef01": HomecastDevice(
                unique_id="my_home_0bf8.living_room_a1b2.light_group_ef01",
                name="Light Group",
                room_name="Living Room",
                home_key="my_home_0bf8",
                home_name="My Home",
                room_key="living_room_a1b2",
                accessory_key="light_group_ef01",
                device_type="light",
                state={"on": True, "brightness": 80},
                settable=["on", "brightness"],
            ),
        },
        homes={
            "my_home_0bf8": HomecastHome(
                key="my_home_0bf8",
                name="My Home",
                home_id="EEBCDDC0-F66D-5BD2-8D0E-C28CEC3FB454",
            ),
        },
        member_to_group={
            "my_home_0bf8.living_room_a1b2.ceiling_light_c3d4": "my_home_0bf8.living_room_a1b2.light_group_ef01",
        },
    )

    mock_homecast.get_state = AsyncMock(
        side_effect=lambda **kw: copy.deepcopy(group_state)
    )

    coordinator = await _setup_and_get_coordinator(
        hass, mock_homecast, mock_config_entry
    )

    group_key = "my_home_0bf8.living_room_a1b2.light_group_ef01"
    original_state = dict(coordinator.data.devices[group_key].state)

    # Send an update with unknown characteristic type — member state won't update,
    # so _apply_state_update returns None and group propagation doesn't happen
    coordinator._on_ws_message(
        {
            "type": "characteristic_update",
            "homeId": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXX0BF8",
            "accessoryId": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXC3D4",
            "characteristicType": "unknown_type",
            "value": 99,
        }
    )

    # Group state should remain unchanged
    assert coordinator.data.devices[group_key].state == original_state


async def test_async_set_state_auth_error(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_set_state raises ConfigEntryAuthFailed on HomecastAuthError."""
    coordinator = await _setup_and_get_coordinator(
        hass, mock_homecast, mock_config_entry
    )

    mock_homecast.set_state.side_effect = HomecastAuthError("unauthorized")

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator.async_set_state({"some": "update"})


async def test_async_set_state_generic_error(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_set_state logs error on HomecastError but does not raise."""
    coordinator = await _setup_and_get_coordinator(
        hass, mock_homecast, mock_config_entry
    )

    mock_homecast.set_state.side_effect = HomecastError("device timeout")

    # Should NOT raise — the error is logged and refresh is still requested
    await coordinator.async_set_state({"some": "update"})


async def test_ws_setup_no_ws_returns_early(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_setup_websocket returns immediately when ws is None."""
    mock_config_entry.add_to_hass(hass)

    coordinator = HomecastCoordinator(
        hass,
        mock_config_entry,
        mock_homecast,
        refresh_token=AsyncMock(return_value="token"),
        ws=None,
        initial_token="token",
    )

    # Should not raise — just returns early
    await coordinator.async_setup_websocket()
    assert coordinator.update_interval.total_seconds() == 30


async def test_apply_state_update_device_removed(
    hass: HomeAssistant,
    mock_homecast: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test _apply_state_update returns None when device was removed from data."""
    coordinator = await _setup_and_get_coordinator(
        hass, mock_homecast, mock_config_entry
    )

    # Remove the device from data but keep the UUID mapping stale
    device_key = "my_home_0bf8.living_room_a1b2.ceiling_light_c3d4"
    del coordinator.data.devices[device_key]

    result = coordinator._apply_state_update(
        "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXX0BF8",
        "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXC3D4",
        "on",
        False,
    )
    assert result is None
