"""Tests for the Easywave coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.easywave.const import DEVICE_SCAN_INTERVAL, DOMAIN
from homeassistant.components.easywave.coordinator import EasywaveCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


@pytest.fixture
def mock_transceiver() -> MagicMock:
    """Return a mock RX11Transceiver."""
    transceiver = MagicMock()
    transceiver.is_connected = True
    transceiver.device_path = "/dev/ttyACM0"
    transceiver.usb_serial_number = "12345"
    transceiver.hw_version = "1.0"
    transceiver.fw_version = "2.0"
    transceiver.connect = AsyncMock(return_value=True)
    transceiver.reconnect = AsyncMock(return_value=True)
    transceiver.disconnect = AsyncMock()
    transceiver.set_disconnect_callback = MagicMock()
    return transceiver


@pytest.fixture
def mock_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Easywave Gateway",
        data={"device_path": "/dev/ttyACM0"},
    )


@pytest.fixture
def coordinator(
    hass: HomeAssistant,
    mock_transceiver: MagicMock,
    mock_entry: MockConfigEntry,
) -> EasywaveCoordinator:
    """Return an EasywaveCoordinator instance."""
    mock_entry.add_to_hass(hass)
    return EasywaveCoordinator(hass, mock_transceiver, mock_entry)


def test_coordinator_init(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
    mock_entry: MockConfigEntry,
) -> None:
    """Test coordinator initialisation."""
    assert coordinator.transceiver is mock_transceiver
    assert coordinator.config_entry is mock_entry
    assert coordinator.name == DOMAIN
    assert coordinator.update_interval == DEVICE_SCAN_INTERVAL
    assert coordinator.is_offline is False


def test_coordinator_init_offline(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
) -> None:
    """Test coordinator initialises as offline when transceiver not connected."""
    mock_entry.add_to_hass(hass)
    transceiver = MagicMock()
    transceiver.is_connected = False
    coord = EasywaveCoordinator(hass, transceiver, mock_entry)
    assert coord.is_offline is True


# ── async_setup ─────────────────────────────────────────────────────────────


async def test_async_setup_connected(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
) -> None:
    """Test successful setup when transceiver connects."""
    result = await coordinator.async_setup()

    assert result is True
    assert coordinator.is_offline is False
    mock_transceiver.connect.assert_awaited_once()
    mock_transceiver.set_disconnect_callback.assert_called_once()


async def test_async_setup_offline(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
) -> None:
    """Test setup enters offline mode when transceiver cannot connect."""
    mock_transceiver.connect = AsyncMock(return_value=False)

    result = await coordinator.async_setup()

    assert result is True
    assert coordinator.is_offline is True
    mock_transceiver.set_disconnect_callback.assert_not_called()


async def test_async_setup_exception(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
) -> None:
    """Test setup returns False on exception."""
    mock_transceiver.connect = AsyncMock(side_effect=OSError("port error"))

    result = await coordinator.async_setup()

    assert result is False


# ── disconnect handling ─────────────────────────────────────────────────────


async def test_on_transceiver_disconnect(
    hass: HomeAssistant,
    coordinator: EasywaveCoordinator,
) -> None:
    """Test _on_transceiver_disconnect schedules _handle_disconnect."""
    coordinator.is_offline = False
    coordinator._on_transceiver_disconnect()
    # Allow the call_soon_threadsafe callback to execute
    await hass.async_block_till_done()
    assert coordinator.is_offline is True


async def test_handle_disconnect_already_offline(
    coordinator: EasywaveCoordinator,
) -> None:
    """Test _handle_disconnect is a no-op when already offline."""
    coordinator.is_offline = True
    # Should not raise or change anything
    coordinator._handle_disconnect()
    assert coordinator.is_offline is True


async def test_handle_disconnect_sets_offline(
    coordinator: EasywaveCoordinator,
) -> None:
    """Test _handle_disconnect marks offline and pushes data."""
    coordinator.is_offline = False
    coordinator.async_set_updated_data = MagicMock()

    coordinator._handle_disconnect()

    assert coordinator.is_offline is True
    coordinator.async_set_updated_data.assert_called_once_with(
        {
            "is_connected": False,
            "device_path": None,
        }
    )


# ── _async_update_data ──────────────────────────────────────────────────────


async def test_update_data_online(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
) -> None:
    """Test update returns connected data when online."""
    coordinator.is_offline = False

    data = await coordinator._async_update_data()

    assert data == {
        "is_connected": True,
        "device_path": "/dev/ttyACM0",
    }


async def test_update_data_reconnect_success(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
) -> None:
    """Test update reconnects successfully from offline."""
    coordinator.is_offline = True
    mock_transceiver.reconnect = AsyncMock(return_value=True)

    data = await coordinator._async_update_data()

    assert coordinator.is_offline is False
    mock_transceiver.set_disconnect_callback.assert_called()
    assert data["is_connected"] is True


async def test_update_data_reconnect_fails(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
) -> None:
    """Test update stays offline when reconnect fails."""
    coordinator.is_offline = True
    mock_transceiver.reconnect = AsyncMock(return_value=False)

    data = await coordinator._async_update_data()

    assert coordinator.is_offline is True
    assert data == {"is_connected": False, "device_path": None}


async def test_update_data_detects_lost_connection(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
) -> None:
    """Test update detects connection loss during poll."""
    coordinator.is_offline = False
    mock_transceiver.is_connected = False

    data = await coordinator._async_update_data()

    assert coordinator.is_offline is True
    assert data == {"is_connected": False, "device_path": None}


async def test_update_data_update_failed(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
) -> None:
    """Test UpdateFailed is re-raised and sets offline."""
    coordinator.is_offline = True
    mock_transceiver.reconnect = AsyncMock(side_effect=UpdateFailed("fail"))

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    assert coordinator.is_offline is True


async def test_update_data_generic_exception(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
) -> None:
    """Test OS error during reconnect is wrapped in UpdateFailed."""
    coordinator.is_offline = True
    mock_transceiver.reconnect = AsyncMock(side_effect=OSError("boom"))

    with pytest.raises(UpdateFailed, match="boom"):
        await coordinator._async_update_data()

    assert coordinator.is_offline is True


# ── async_shutdown ──────────────────────────────────────────────────────────


async def test_async_shutdown(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
) -> None:
    """Test clean shutdown disconnects transceiver."""
    await coordinator.async_shutdown()

    mock_transceiver.disconnect.assert_awaited_once()


async def test_async_shutdown_error(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
) -> None:
    """Test shutdown handles errors gracefully."""
    mock_transceiver.disconnect = AsyncMock(side_effect=OSError("port busy"))

    # Should not raise
    await coordinator.async_shutdown()

    mock_transceiver.disconnect.assert_awaited_once()
