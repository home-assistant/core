"""Tests for Specialized Turbo coordinator."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

from bleak import BleakError
from specialized_turbo import CHAR_NOTIFY

from homeassistant.components.specialized_turbo.coordinator import (
    SpecializedTurboCoordinator,
)
from homeassistant.core import HomeAssistant

from .conftest import MOCK_ADDRESS

_LOGGER = logging.getLogger(__name__)


def _make_coordinator(
    hass: HomeAssistant, pin: int | None = None
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

    # Simulate first connection with data received
    mock_client = MagicMock()
    mock_client.is_connected = True
    coord._client = mock_client
    coord.snapshot.message_count = 100
    assert coord._needs_poll(MagicMock(), None) is False

    # Simulate bike leaving (disconnect callback fires)
    coord._on_disconnect(mock_client)
    assert coord._client is None

    # Bike comes back in range — needs_poll must return True to reconnect
    assert coord._needs_poll(MagicMock(), None) is True


# --- async_poll ---


async def test_async_poll(hass: HomeAssistant) -> None:
    """Test that polling calls _ensure_connected."""
    coord = _make_coordinator(hass)

    with patch.object(coord, "_ensure_connected", new_callable=AsyncMock) as mock:
        await coord._do_poll()
        mock.assert_called_once()


# --- notification_handler ---


async def test_notification_handler_valid(hass: HomeAssistant) -> None:
    """Test notification handler parses valid data and updates snapshot."""
    coord = _make_coordinator(hass)

    # Battery charge percent: sender=0x00, channel=0x0C, value=85 (0x55)
    data = bytearray([0x00, 0x0C, 0x55])
    coord._notification_handler(0, data)

    assert coord.snapshot.battery.charge_pct == 85
    assert coord.snapshot.message_count == 1


async def test_notification_handler_speed(hass: HomeAssistant) -> None:
    """Test notification handler with speed value."""
    coord = _make_coordinator(hass)

    # Speed: sender=0x01, channel=0x02, value=255 (25.5 km/h) as 2 bytes LE
    data = bytearray([0x01, 0x02, 0xFF, 0x00])
    coord._notification_handler(0, data)

    assert coord.snapshot.motor.speed_kmh == 25.5
    assert coord.snapshot.message_count == 1


async def test_notification_handler_parse_error(hass: HomeAssistant) -> None:
    """Test notification handler handles parse errors gracefully."""
    coord = _make_coordinator(hass)

    # Too short to parse (< 3 bytes)
    data = bytearray([0x00])
    coord._notification_handler(0, data)

    assert coord.snapshot.message_count == 0


async def test_notification_handler_unknown_field(hass: HomeAssistant) -> None:
    """Test notification handler handles unknown fields."""
    coord = _make_coordinator(hass)

    # Unknown sender 0x03
    data = bytearray([0x03, 0x00, 0x42])
    coord._notification_handler(0, data)

    assert coord.snapshot.message_count == 1


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
    coord = _make_coordinator(hass, pin=1234)

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
    coord = _make_coordinator(hass, pin=1234)

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
    coord = _make_coordinator(hass, pin=1234)

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

    coord._on_disconnect(MagicMock())

    assert coord._was_unavailable is True
    assert coord._client is None
    coord.async_update_listeners.assert_called_once()


async def test_on_disconnect_already_unavailable(hass: HomeAssistant) -> None:
    """Test disconnect when already unavailable doesn't re-log."""
    coord = _make_coordinator(hass)
    coord._was_unavailable = True
    coord._client = MagicMock()

    coord._on_disconnect(MagicMock())

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
    """Test that BleakError during start_notify is caught and client is cleared."""
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
    ):
        await coord._do_poll()  # should not raise

    assert coord._client is None


async def test_do_poll_bleak_error_from_establish_connection(
    hass: HomeAssistant,
) -> None:
    """Test that BleakError during establish_connection is caught."""
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
    ):
        await coord._do_poll()  # should not raise

    assert coord._client is None
