"""Tests for Specialized Turbo coordinator."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

from bleak import BleakError
import pytest
from specialized_turbo import CHAR_NOTIFY, CHAR_NOTIFY_TCU1, AssistLevel, BLEProfile

from homeassistant.components.specialized_turbo.coordinator import (
    SpecializedTurboCoordinator,
)
from homeassistant.core import HomeAssistant

from .conftest import MOCK_ADDRESS, MOCK_TCU1_MANUFACTURER_DATA

_LOGGER = logging.getLogger(__name__)


def _make_coordinator(
    hass: HomeAssistant, pin: str | None = None
) -> SpecializedTurboCoordinator:
    """Create a coordinator with mocked parent class."""
    with patch(
        "homeassistant.components.specialized_turbo.coordinator.ActiveBluetoothDataUpdateCoordinator.__init__",
        return_value=None,
    ):
        coord = SpecializedTurboCoordinator(
            hass, _LOGGER, address=MOCK_ADDRESS, pin=pin
        )
    coord.hass = hass
    coord.async_update_listeners = MagicMock()
    return coord


# --- needs_poll ---


async def test_needs_poll_no_client(hass: HomeAssistant) -> None:
    """Test needs_poll returns True when no client exists."""
    coord = _make_coordinator(hass)
    assert coord._needs_poll(MagicMock(), None) is True


async def test_needs_poll_connected(hass: HomeAssistant) -> None:
    """Test needs_poll returns False when client is connected."""
    coord = _make_coordinator(hass)
    mock_client = MagicMock()
    mock_client.is_connected = True
    coord._client = mock_client
    assert coord._needs_poll(MagicMock(), None) is False


async def test_needs_poll_disconnected_client(hass: HomeAssistant) -> None:
    """Test needs_poll returns True when client exists but is disconnected."""
    coord = _make_coordinator(hass)
    mock_client = MagicMock()
    mock_client.is_connected = False
    coord._client = mock_client
    assert coord._needs_poll(MagicMock(), None) is True


async def test_needs_poll_after_disconnect_reconnect(hass: HomeAssistant) -> None:
    """Test needs_poll triggers reconnection after bike leaves and returns."""
    coord = _make_coordinator(hass)

    mock_client = MagicMock()
    mock_client.is_connected = True
    coord._client = mock_client
    coord.snapshot.message_count = 100
    assert coord._needs_poll(MagicMock(), None) is False

    coord._handle_disconnect()
    assert coord._client is None

    assert coord._needs_poll(MagicMock(), None) is True


# --- do_poll ---


async def test_do_poll(hass: HomeAssistant) -> None:
    """Test that polling calls _ensure_connected."""
    coord = _make_coordinator(hass)

    with patch.object(coord, "_ensure_connected", new_callable=AsyncMock) as mock:
        await coord._do_poll()
        mock.assert_called_once()


# --- notification_handler ---


async def test_notification_handler_valid(hass: HomeAssistant) -> None:
    """Test notification handler parses valid data and updates snapshot."""
    coord = _make_coordinator(hass)

    data = bytearray([0x00, 0x0C, 0x55])
    coord._handle_notification(bytes(data))

    assert coord.snapshot.battery.charge_pct == 85
    assert coord.snapshot.message_count == 1
    coord.async_update_listeners.assert_called_once()


async def test_notification_handler_speed(hass: HomeAssistant) -> None:
    """Test notification handler with speed value."""
    coord = _make_coordinator(hass)

    data = bytearray([0x01, 0x02, 0xFF, 0x00])
    coord._handle_notification(bytes(data))

    assert coord.snapshot.motor.speed_kmh == 25.5
    assert coord.snapshot.message_count == 1


async def test_notification_handler_parse_error(hass: HomeAssistant) -> None:
    """Test notification handler handles parse errors gracefully."""
    coord = _make_coordinator(hass)

    data = bytearray([0x00])
    coord._handle_notification(bytes(data))

    assert coord.snapshot.message_count == 0
    coord.async_update_listeners.assert_not_called()


async def test_notification_handler_unknown_field(hass: HomeAssistant) -> None:
    """Test notification handler handles unknown fields."""
    coord = _make_coordinator(hass)

    data = bytearray([0x03, 0x00, 0x42])
    coord._handle_notification(bytes(data))

    assert coord.snapshot.message_count == 1
    coord.async_update_listeners.assert_called_once()


# --- ensure_connected ---


async def test_ensure_connected_already_connected(hass: HomeAssistant) -> None:
    """Test ensure_connected returns early if already connected."""
    coord = _make_coordinator(hass)

    mock_client = MagicMock()
    mock_client.is_connected = True
    coord._client = mock_client

    await coord._ensure_connected()

    assert coord._client is mock_client


async def test_ensure_connected_device_not_found(hass: HomeAssistant) -> None:
    """Test ensure_connected sets unavailable when device not found."""
    coord = _make_coordinator(hass)

    with patch(
        "homeassistant.components.specialized_turbo.coordinator.bluetooth.async_ble_device_from_address",
        return_value=None,
    ):
        await coord._ensure_connected()

    assert coord._was_unavailable is True
    assert coord._client is None


async def test_ensure_connected_device_not_found_no_repeat_log(
    hass: HomeAssistant,
) -> None:
    """Test that unavailable message is only logged once."""
    coord = _make_coordinator(hass)
    coord._was_unavailable = True

    with patch(
        "homeassistant.components.specialized_turbo.coordinator.bluetooth.async_ble_device_from_address",
        return_value=None,
    ):
        await coord._ensure_connected()

    assert coord._was_unavailable is True


async def test_ensure_connected_success(hass: HomeAssistant) -> None:
    """Test ensure_connected connects and subscribes to notifications."""
    coord = _make_coordinator(hass)

    mock_client = AsyncMock()
    mock_client.is_connected = True

    with (
        patch(
            "homeassistant.components.specialized_turbo.coordinator.bluetooth.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.specialized_turbo.coordinator.establish_connection",
            new_callable=AsyncMock,
            return_value=mock_client,
        ),
    ):
        await coord._ensure_connected()

    assert coord._client is mock_client
    mock_client.start_notify.assert_called_once_with(
        CHAR_NOTIFY, coord._notification_handler
    )


async def test_ensure_connected_reconnect_after_unavailable(
    hass: HomeAssistant,
) -> None:
    """Test that reconnection after unavailable clears the flag."""
    coord = _make_coordinator(hass)
    coord._was_unavailable = True

    mock_client = AsyncMock()

    with (
        patch(
            "homeassistant.components.specialized_turbo.coordinator.bluetooth.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.specialized_turbo.coordinator.establish_connection",
            new_callable=AsyncMock,
            return_value=mock_client,
        ),
    ):
        await coord._ensure_connected()

    assert coord._was_unavailable is False
    assert coord._client is mock_client


async def test_ensure_connected_with_pin(hass: HomeAssistant) -> None:
    """Test ensure_connected triggers pairing when PIN is set."""
    coord = _make_coordinator(hass, pin="1234")

    mock_client = AsyncMock()

    with (
        patch(
            "homeassistant.components.specialized_turbo.coordinator.bluetooth.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.specialized_turbo.coordinator.establish_connection",
            new_callable=AsyncMock,
            return_value=mock_client,
        ),
    ):
        await coord._ensure_connected()

    mock_client.pair.assert_called_once_with(protection_level=2)


async def test_ensure_connected_pairing_not_implemented(
    hass: HomeAssistant,
) -> None:
    """Test pairing gracefully handles NotImplementedError."""
    coord = _make_coordinator(hass, pin="1234")

    mock_client = AsyncMock()
    mock_client.pair.side_effect = NotImplementedError

    with (
        patch(
            "homeassistant.components.specialized_turbo.coordinator.bluetooth.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.specialized_turbo.coordinator.establish_connection",
            new_callable=AsyncMock,
            return_value=mock_client,
        ),
    ):
        await coord._ensure_connected()

    mock_client.start_notify.assert_called_once()


async def test_ensure_connected_pairing_error(hass: HomeAssistant) -> None:
    """Test pairing gracefully handles generic errors."""
    coord = _make_coordinator(hass, pin="1234")

    mock_client = AsyncMock()
    mock_client.pair.side_effect = RuntimeError("Pair failed")

    with (
        patch(
            "homeassistant.components.specialized_turbo.coordinator.bluetooth.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.specialized_turbo.coordinator.establish_connection",
            new_callable=AsyncMock,
            return_value=mock_client,
        ),
    ):
        await coord._ensure_connected()

    mock_client.start_notify.assert_called_once()


# --- connected property ---


async def test_connected_no_client(hass: HomeAssistant) -> None:
    """Test connected is False when no client exists."""
    coord = _make_coordinator(hass)
    assert coord.connected is False


async def test_connected_when_connected(hass: HomeAssistant) -> None:
    """Test connected is True when client is connected."""
    coord = _make_coordinator(hass)
    mock_client = MagicMock()
    mock_client.is_connected = True
    coord._client = mock_client
    assert coord.connected is True


async def test_connected_when_disconnected(hass: HomeAssistant) -> None:
    """Test connected is False when client exists but is disconnected."""
    coord = _make_coordinator(hass)
    mock_client = MagicMock()
    mock_client.is_connected = False
    coord._client = mock_client
    assert coord.connected is False


# --- on_disconnect ---


async def test_on_disconnect(hass: HomeAssistant) -> None:
    """Test disconnect callback sets unavailable flag and notifies listeners."""
    coord = _make_coordinator(hass)
    coord._client = MagicMock()

    coord._handle_disconnect()

    assert coord._was_unavailable is True
    assert coord._client is None
    coord.async_update_listeners.assert_called_once()


async def test_on_disconnect_already_unavailable(hass: HomeAssistant) -> None:
    """Test disconnect when already unavailable doesn't re-log."""
    coord = _make_coordinator(hass)
    coord._was_unavailable = True
    coord._client = MagicMock()

    coord._handle_disconnect()

    assert coord._was_unavailable is True
    assert coord._client is None
    coord.async_update_listeners.assert_called_once()


# --- async_shutdown ---


async def test_async_shutdown_connected(hass: HomeAssistant) -> None:
    """Test shutdown cleanly disconnects a connected client."""
    coord = _make_coordinator(hass)
    mock_client = AsyncMock()
    mock_client.is_connected = True
    coord._client = mock_client

    await coord.async_shutdown()

    mock_client.stop_notify.assert_called_once_with(CHAR_NOTIFY)
    mock_client.disconnect.assert_called_once()
    assert coord._client is None


async def test_async_shutdown_not_connected(hass: HomeAssistant) -> None:
    """Test shutdown with no active connection."""
    coord = _make_coordinator(hass)

    await coord.async_shutdown()

    assert coord._client is None


async def test_async_shutdown_errors(hass: HomeAssistant) -> None:
    """Test shutdown handles errors during cleanup."""
    coord = _make_coordinator(hass)
    mock_client = AsyncMock()
    mock_client.is_connected = True
    mock_client.stop_notify.side_effect = Exception("stop error")
    mock_client.disconnect.side_effect = Exception("disconnect error")
    coord._client = mock_client

    await coord.async_shutdown()

    assert coord._client is None


# --- BleakError handling in _do_poll ---


async def test_do_poll_bleak_error_from_start_notify(hass: HomeAssistant) -> None:
    """Test that BleakError during start_notify propagates and client is cleared."""
    coord = _make_coordinator(hass)

    mock_client = AsyncMock()
    mock_client.is_connected = True
    mock_client.start_notify.side_effect = BleakError("Not connected")

    with (
        patch(
            "homeassistant.components.specialized_turbo.coordinator.bluetooth.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.specialized_turbo.coordinator.establish_connection",
            new_callable=AsyncMock,
            return_value=mock_client,
        ),
        pytest.raises(BleakError),
    ):
        await coord._do_poll()

    assert coord._client is None


async def test_do_poll_bleak_error_from_establish_connection(
    hass: HomeAssistant,
) -> None:
    """Test that BleakError during establish_connection propagates."""
    coord = _make_coordinator(hass)

    with (
        patch(
            "homeassistant.components.specialized_turbo.coordinator.bluetooth.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.specialized_turbo.coordinator.establish_connection",
            new_callable=AsyncMock,
            side_effect=BleakError("Failed to connect"),
        ),
        pytest.raises(BleakError),
    ):
        await coord._do_poll()

    assert coord._client is None


# --- TCU1 support ---


async def test_needs_poll_detects_tcu1(hass: HomeAssistant) -> None:
    """Test _needs_poll detects TCU1 protocol from manufacturer data."""
    coord = _make_coordinator(hass)
    service_info = MagicMock()
    service_info.manufacturer_data = MOCK_TCU1_MANUFACTURER_DATA
    coord._needs_poll(service_info, None)
    assert coord._generation == BLEProfile.TCU1


async def test_ensure_connected_tcu1_uses_tcu1_char_notify(
    hass: HomeAssistant,
) -> None:
    """Test ensure_connected subscribes to TCU1 CHAR_NOTIFY UUID."""
    coord = _make_coordinator(hass)
    coord._generation = BLEProfile.TCU1

    mock_client = AsyncMock()
    mock_client.is_connected = True

    with (
        patch(
            "homeassistant.components.specialized_turbo.coordinator.bluetooth.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.specialized_turbo.coordinator.establish_connection",
            new_callable=AsyncMock,
            return_value=mock_client,
        ),
    ):
        await coord._ensure_connected()

    mock_client.start_notify.assert_called_once_with(
        CHAR_NOTIFY_TCU1, coord._notification_handler
    )


async def test_tcu1_notification_with_ff_padding(hass: HomeAssistant) -> None:
    """Test TCU1 notifications with FF padding parse correctly."""
    coord = _make_coordinator(hass)
    coord._generation = BLEProfile.TCU1

    data = bytearray.fromhex("01050100" + "ff" * 16)
    coord._handle_notification(bytes(data))

    assert coord.snapshot.motor.assist_level == AssistLevel.ECO
    assert coord.snapshot.message_count == 1
