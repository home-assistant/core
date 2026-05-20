"""Tests for Specialized Turbo BLE coordinator."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from specialized_turbo import BLEProfile

from homeassistant.components.specialized_turbo.coordinator import (
    _POLL_INTERVAL,
    SpecializedTurboCoordinator,
)
from homeassistant.core import HomeAssistant

from .conftest import MOCK_ADDRESS, TCX_SERVICE_INFO


def _create_coordinator(
    hass: HomeAssistant,
    address: str = MOCK_ADDRESS,
) -> SpecializedTurboCoordinator:
    """Create a coordinator for testing."""
    return SpecializedTurboCoordinator(
        hass,
        logging.getLogger(__name__),
        address=address,
    )


# --- _needs_poll tests ---


def test_needs_poll_when_disconnected(hass: HomeAssistant) -> None:
    """Test _needs_poll returns True when BLE client is not connected."""
    coordinator = _create_coordinator(hass)
    assert coordinator._needs_poll(TCX_SERVICE_INFO, None) is True


def test_needs_poll_when_connected_and_never_polled(hass: HomeAssistant) -> None:
    """Test _needs_poll returns True when connected but initial poll hasn't completed."""
    coordinator = _create_coordinator(hass)
    coordinator._client = MagicMock(is_connected=True)
    assert coordinator._needs_poll(TCX_SERVICE_INFO, None) is True


def test_needs_poll_when_interval_elapsed(hass: HomeAssistant) -> None:
    """Test _needs_poll returns True when poll attempt interval has elapsed."""
    coordinator = _create_coordinator(hass)
    coordinator._client = MagicMock(is_connected=True)

    assert coordinator._needs_poll(TCX_SERVICE_INFO, _POLL_INTERVAL) is True


def test_needs_poll_when_interval_not_elapsed(hass: HomeAssistant) -> None:
    """Test _needs_poll returns False when a recent poll attempt exists."""
    coordinator = _create_coordinator(hass)
    coordinator._client = MagicMock(is_connected=True)

    assert coordinator._needs_poll(TCX_SERVICE_INFO, _POLL_INTERVAL - 1) is False


def test_needs_poll_detects_generation(hass: HomeAssistant) -> None:
    """Test _needs_poll detects generation from advertisement manufacturer data."""
    coordinator = _create_coordinator(hass)
    assert coordinator._generation is None

    coordinator._needs_poll(TCX_SERVICE_INFO, None)

    assert coordinator._generation is not None


# --- Notification handling tests ---


def test_handle_notification_updates_snapshot(hass: HomeAssistant) -> None:
    """Test _handle_notification parses data and updates listeners."""
    coordinator = _create_coordinator(hass)
    listener = MagicMock()
    coordinator.async_add_listener(listener)

    mock_msg = MagicMock()
    with patch(
        "homeassistant.components.specialized_turbo.coordinator.parse_notification",
        return_value=mock_msg,
    ):
        coordinator._handle_notification(b"\x01\x02\x03")

    # Listener called means parse + update_from_message + async_update_listeners ran.
    listener.assert_called()


def test_handle_notification_ignores_parse_error(hass: HomeAssistant) -> None:
    """Test _handle_notification gracefully handles parse errors."""
    coordinator = _create_coordinator(hass)
    listener = MagicMock()
    coordinator.async_add_listener(listener)

    with patch(
        "homeassistant.components.specialized_turbo.coordinator.parse_notification",
        side_effect=ValueError("bad data"),
    ):
        coordinator._handle_notification(b"\xff\xff")

    listener.assert_not_called()


# --- Disconnect handling tests ---


def test_handle_disconnect_clears_client(hass: HomeAssistant) -> None:
    """Test _handle_disconnect resets client and notifies listeners."""
    coordinator = _create_coordinator(hass)
    coordinator._client = MagicMock(is_connected=True)
    listener = MagicMock()
    coordinator.async_add_listener(listener)

    coordinator._handle_disconnect()

    assert coordinator._client is None
    assert coordinator._was_unavailable is True
    listener.assert_called()


# --- Connected property tests ---


def test_connected_when_client_is_connected(hass: HomeAssistant) -> None:
    """Test connected property returns True when BLE client is connected."""
    coordinator = _create_coordinator(hass)
    coordinator._client = MagicMock(is_connected=True)
    assert coordinator.connected is True


def test_connected_when_client_is_none(hass: HomeAssistant) -> None:
    """Test connected property returns False when no BLE client."""
    coordinator = _create_coordinator(hass)
    assert coordinator.connected is False


def test_connected_when_client_disconnected(hass: HomeAssistant) -> None:
    """Test connected property returns False when BLE client is disconnected."""
    coordinator = _create_coordinator(hass)
    coordinator._client = MagicMock(is_connected=False)
    assert coordinator.connected is False


# --- Polling with late generation detection ---


async def test_do_poll_derives_chars_for_late_generation(
    hass: HomeAssistant,
) -> None:
    """Test _do_poll derives char UUIDs when generation is detected after connection."""
    coordinator = _create_coordinator(hass)
    coordinator._client = MagicMock(is_connected=True)
    coordinator._generation = BLEProfile.TCX
    # Chars not set (simulating connection made before generation was known)
    assert coordinator._char_request_write is None
    assert coordinator._char_request_read is None

    with (
        patch.object(coordinator, "_ensure_connected", new_callable=AsyncMock),
        patch(
            "homeassistant.components.specialized_turbo.coordinator.poll_tcx",
            new_callable=AsyncMock,
        ),
    ):
        await coordinator._do_poll(TCX_SERVICE_INFO)

    assert coordinator._char_request_write is not None
    assert coordinator._char_request_read is not None


async def test_do_poll_warns_once_when_generation_unresolved(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test _do_poll logs a single warning when chars cannot be resolved."""
    coordinator = _create_coordinator(hass)
    coordinator._client = MagicMock(is_connected=True)
    # Generation never detected — chars stay None.
    assert coordinator._generation is None

    with (
        patch.object(coordinator, "_ensure_connected", new_callable=AsyncMock),
        caplog.at_level("WARNING"),
    ):
        await coordinator._do_poll(TCX_SERVICE_INFO)
        await coordinator._do_poll(TCX_SERVICE_INFO)

    matching = [r for r in caplog.records if "could not determine" in r.message]
    assert len(matching) == 1
