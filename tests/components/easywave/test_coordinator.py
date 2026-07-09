"""Tests for the Easywave coordinator."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.easywave.const import DEVICE_SCAN_INTERVAL, DOMAIN
from homeassistant.components.easywave.coordinator import EasywaveCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import UpdateFailed

from .conftest import MOCK_GATEWAY_TITLE, mock_easywave_transceiver

from tests.common import MockConfigEntry


@pytest.fixture
def mock_transceiver() -> MagicMock:
    """Return a mock RX11Transceiver at the hardware boundary."""
    return mock_easywave_transceiver()


@pytest.fixture
def mock_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_GATEWAY_TITLE,
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
    mock_entry.mock_state(hass, ConfigEntryState.SETUP_IN_PROGRESS)
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


async def test_first_refresh_registers_gateway_versions(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Successful first refresh connects and registers gateway versions."""
    await coordinator.async_config_entry_first_refresh()

    assert coordinator.is_offline is False
    mock_transceiver.connect.assert_awaited_once()
    mock_transceiver.set_disconnect_callback.assert_called_once()
    mock_transceiver.set_connected_callback.assert_called_once()

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, coordinator.config_entry.entry_id)}
    )
    assert device is not None
    assert device.hw_version == "1.0"
    assert device.sw_version == "2.0"


async def test_first_refresh_enters_offline_mode_when_connect_fails(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
) -> None:
    """First refresh enters offline mode when the transceiver cannot connect."""
    mock_transceiver.connect = AsyncMock(return_value=False)
    mock_transceiver.reconnect = AsyncMock(return_value=False)

    await coordinator.async_config_entry_first_refresh()

    assert coordinator.is_offline is True
    mock_transceiver.set_disconnect_callback.assert_not_called()


async def test_first_refresh_raises_update_failed_on_connect_error(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
) -> None:
    """First refresh raises ConfigEntryNotReady when connect raises."""
    mock_transceiver.connect = AsyncMock(side_effect=OSError("port error"))

    with pytest.raises(ConfigEntryNotReady):
        await coordinator.async_config_entry_first_refresh()

    assert coordinator.last_update_success is False
    assert isinstance(coordinator.last_exception, UpdateFailed)


async def test_transceiver_disconnect_marks_coordinator_offline(
    hass: HomeAssistant,
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
) -> None:
    """Transceiver disconnect callback marks the coordinator offline."""
    await coordinator.async_config_entry_first_refresh()
    coordinator.is_offline = False
    disconnect_callback = mock_transceiver.set_disconnect_callback.call_args[0][0]

    disconnect_callback()
    await hass.async_block_till_done()

    assert coordinator.is_offline is True
    assert coordinator.data == {
        "is_connected": False,
        "device_path": None,
    }


async def test_transceiver_disconnect_is_noop_when_already_offline(
    hass: HomeAssistant,
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
) -> None:
    """Repeated disconnect callbacks do not change an offline coordinator."""
    await coordinator.async_config_entry_first_refresh()
    disconnect_callback = mock_transceiver.set_disconnect_callback.call_args[0][0]
    coordinator.is_offline = True

    disconnect_callback()
    await hass.async_block_till_done()

    assert coordinator.is_offline is True


async def test_refresh_returns_connected_data_when_online(
    coordinator: EasywaveCoordinator,
) -> None:
    """Periodic refresh returns connected data when online."""
    await coordinator.async_config_entry_first_refresh()

    await coordinator.async_refresh()

    assert coordinator.data == {
        "is_connected": True,
        "device_path": "/dev/ttyACM0",
    }


async def test_refresh_reconnects_and_updates_gateway_versions(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Periodic refresh reconnects from offline and updates gateway versions."""
    device_registry.async_get_or_create(
        config_entry_id=coordinator.config_entry.entry_id,
        identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
        name="RX11 USB Transceiver",
    )
    await coordinator.async_config_entry_first_refresh()
    coordinator.is_offline = True
    mock_transceiver.reconnect = AsyncMock(return_value=True)
    mock_transceiver.hw_version = "RX11 v1.0"
    mock_transceiver.fw_version = "FW 2.3.4"

    await coordinator.async_refresh()

    assert coordinator.is_offline is False
    assert coordinator.data["is_connected"] is True
    mock_transceiver.set_connected_callback.assert_called()

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, coordinator.config_entry.entry_id)}
    )
    assert device is not None
    assert device.hw_version == "RX11 v1.0"
    assert device.sw_version == "FW 2.3.4"


async def test_refresh_stays_offline_when_reconnect_fails(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
) -> None:
    """Periodic refresh stays offline when reconnect fails."""
    await coordinator.async_config_entry_first_refresh()
    coordinator.is_offline = True
    mock_transceiver.reconnect = AsyncMock(return_value=False)

    await coordinator.async_refresh()

    assert coordinator.is_offline is True
    assert coordinator.data == {"is_connected": False, "device_path": None}


async def test_refresh_detects_lost_connection(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
) -> None:
    """Periodic refresh detects connection loss during polling."""
    await coordinator.async_config_entry_first_refresh()
    mock_transceiver.is_connected = False

    await coordinator.async_refresh()

    assert coordinator.is_offline is True
    assert coordinator.data == {"is_connected": False, "device_path": None}


async def test_refresh_reraises_update_failed(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
) -> None:
    """UpdateFailed from reconnect is recorded during refresh."""
    await coordinator.async_config_entry_first_refresh()
    coordinator.is_offline = True
    mock_transceiver.reconnect = AsyncMock(side_effect=UpdateFailed("fail"))

    await coordinator.async_refresh()

    assert coordinator.is_offline is True
    assert coordinator.last_update_success is False
    assert isinstance(coordinator.last_exception, UpdateFailed)


async def test_refresh_wraps_os_error_in_update_failed(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
) -> None:
    """OS errors during reconnect are wrapped in UpdateFailed."""
    await coordinator.async_config_entry_first_refresh()
    coordinator.is_offline = True
    mock_transceiver.reconnect = AsyncMock(side_effect=OSError("boom"))

    await coordinator.async_refresh()

    assert coordinator.is_offline is True
    assert coordinator.last_update_success is False
    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert str(coordinator.last_exception) == "Update failed: boom"


async def test_telegram_listener_restarts_after_suspend_resume(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
) -> None:
    """Suspending and resuming the listener restarts telegram polling."""

    async def receive_side_effect(timeout: float = 30.0) -> None:
        raise asyncio.CancelledError

    mock_transceiver.receive_telegram = AsyncMock(side_effect=receive_side_effect)

    await coordinator.async_config_entry_first_refresh()
    entity = MagicMock()
    try:
        coordinator.register_sensor_entities([entity])
        await coordinator.hass.async_block_till_done(wait_background_tasks=True)

        await coordinator.suspend_telegram_listener()
        mock_transceiver.receive_telegram.reset_mock()
        coordinator.resume_telegram_listener()
        await coordinator.hass.async_block_till_done(wait_background_tasks=True)

        mock_transceiver.receive_telegram.assert_called()
    finally:
        await coordinator.suspend_telegram_listener()
        await coordinator.async_shutdown()


async def test_transceiver_connected_updates_gateway_device(
    hass: HomeAssistant,
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Transceiver connect callback refreshes gateway device metadata."""
    device_registry.async_get_or_create(
        config_entry_id=coordinator.config_entry.entry_id,
        identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
        name="RX11 USB Transceiver",
    )
    await coordinator.async_config_entry_first_refresh()
    mock_transceiver.hw_version = "RX11 v2.0"
    connected_callback = mock_transceiver.set_connected_callback.call_args[0][0]

    connected_callback()
    await hass.async_block_till_done()

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, coordinator.config_entry.entry_id)}
    )
    assert device is not None
    assert device.hw_version == "RX11 v2.0"


async def test_async_shutdown(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
) -> None:
    """Test clean shutdown disposes transceiver."""
    await coordinator.async_shutdown()

    mock_transceiver.dispose.assert_awaited_once()


async def test_async_shutdown_error(
    coordinator: EasywaveCoordinator,
    mock_transceiver: MagicMock,
) -> None:
    """Test shutdown handles errors gracefully."""
    mock_transceiver.dispose = AsyncMock(side_effect=OSError("port busy"))

    await coordinator.async_shutdown()

    mock_transceiver.dispose.assert_awaited_once()
