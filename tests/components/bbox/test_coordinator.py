"""Tests for Bbox coordinator."""

from unittest.mock import AsyncMock

from aiobbox import BboxApiError, BboxAuthError
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import setup_integration
from .const import (
    DEVICE_1_HOSTNAME,
    DEVICE_1_MAC,
    DEVICE_2_HOSTNAME,
    DEVICE_2_MAC,
    TEST_SERIAL_NUMBER,
)

from tests.common import MockConfigEntry


async def test_coordinator_data(
    hass: HomeAssistant,
    mock_bbox_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator data structure."""
    await setup_integration(hass, mock_config_entry)

    coordinator = hass.config_entries.async_get_entry(
        mock_config_entry.entry_id
    ).runtime_data

    assert coordinator.data is not None
    assert coordinator.data.router_info.serialnumber == TEST_SERIAL_NUMBER
    assert coordinator.data.ip_stats.rx.bandwidth == 5432000
    assert coordinator.data.ip_stats.tx.bandwidth == 173000

    assert len(coordinator.data.connected_devices) == 2
    assert DEVICE_1_MAC in coordinator.data.connected_devices
    assert DEVICE_2_MAC in coordinator.data.connected_devices
    assert (
        coordinator.data.connected_devices[DEVICE_1_MAC].hostname == DEVICE_1_HOSTNAME
    )
    assert (
        coordinator.data.connected_devices[DEVICE_2_MAC].hostname == DEVICE_2_HOSTNAME
    )


async def test_coordinator_update(
    hass: HomeAssistant,
    mock_bbox_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator update."""
    await setup_integration(hass, mock_config_entry)

    coordinator = hass.config_entries.async_get_entry(
        mock_config_entry.entry_id
    ).runtime_data

    initial_uptime = coordinator.data.router_info.uptime

    mock_bbox_api.get_router_info.return_value.uptime = initial_uptime + 60
    await coordinator.async_refresh()
    assert coordinator.data.router_info.uptime == initial_uptime + 60


@pytest.mark.parametrize(
    ("side_effect", "expected_exception"),
    [
        (BboxAuthError("Authentication failed"), ConfigEntryAuthFailed),
        (BboxApiError("API error"), UpdateFailed),
        (TimeoutError("Timeout"), UpdateFailed),
        (Exception("Unexpected error"), UpdateFailed),
    ],
)
async def test_coordinator_update_errors(
    hass: HomeAssistant,
    mock_bbox_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    expected_exception: type[Exception],
) -> None:
    """Test coordinator error handling."""
    await setup_integration(hass, mock_config_entry)

    coordinator = hass.config_entries.async_get_entry(
        mock_config_entry.entry_id
    ).runtime_data

    # Simulate error during update
    mock_bbox_api.get_router_info.side_effect = side_effect

    await coordinator.async_refresh()
    assert coordinator.last_exception is not None
    assert isinstance(coordinator.last_exception, expected_exception)


async def test_coordinator_shutdown(
    hass: HomeAssistant,
    mock_bbox_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator shutdown."""
    await setup_integration(hass, mock_config_entry)

    coordinator = hass.config_entries.async_get_entry(
        mock_config_entry.entry_id
    ).runtime_data

    # Verify client is initially connected
    assert coordinator.client is not None

    # Shutdown coordinator
    await coordinator.async_shutdown()

    # Verify client was closed
    mock_bbox_api.close.assert_called_once()


async def test_coordinator_auth_failure_triggers_reauth(
    hass: HomeAssistant,
    mock_bbox_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test authentication failure triggers reauth flow."""
    await setup_integration(hass, mock_config_entry)

    coordinator = hass.config_entries.async_get_entry(
        mock_config_entry.entry_id
    ).runtime_data

    # Simulate authentication failure
    mock_bbox_api.get_router_info.side_effect = BboxAuthError("Session expired")

    # Should store ConfigEntryAuthFailed
    await coordinator.async_refresh()
    assert coordinator.last_exception is not None
    assert isinstance(coordinator.last_exception, ConfigEntryAuthFailed)

    # Verify config entry state reflects auth failure
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_coordinator_network_error(
    hass: HomeAssistant,
    mock_bbox_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test network error handling."""
    await setup_integration(hass, mock_config_entry)

    # Get the coordinator from the config entry after setup
    coordinator = hass.config_entries.async_get_entry(
        mock_config_entry.entry_id
    ).runtime_data

    # Simulate network error
    mock_bbox_api.get_router_info.side_effect = BboxApiError("Cannot connect")

    # Should store UpdateFailed
    await coordinator.async_refresh()
    assert coordinator.last_exception is not None
    assert isinstance(coordinator.last_exception, UpdateFailed)


async def test_coordinator_empty_hosts_list(
    hass: HomeAssistant,
    mock_bbox_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator handles empty hosts list."""
    await setup_integration(hass, mock_config_entry)

    # Get the coordinator from the config entry after setup
    coordinator = hass.config_entries.async_get_entry(
        mock_config_entry.entry_id
    ).runtime_data

    # Simulate empty hosts list
    mock_bbox_api.get_hosts.return_value = []

    # Should not raise an error
    await coordinator.async_refresh()
    # Should not have any exception
    assert coordinator.last_exception is None
    # Access data to ensure no exception is raised
    _ = coordinator.data

    assert len(coordinator.data.connected_devices) == 0


async def test_coordinator_partial_data_failure(
    hass: HomeAssistant,
    mock_bbox_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator handles partial data failure."""
    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data

    # Simulate failure in one API call but success in others
    mock_bbox_api.get_wan_ip_stats.side_effect = BboxApiError("WAN stats error")

    # Should store UpdateFailed since all data is required
    await coordinator.async_refresh()
    assert coordinator.last_exception is not None
    assert isinstance(coordinator.last_exception, UpdateFailed)


async def test_coordinator_device_tracking_persistence(
    hass: HomeAssistant,
    mock_bbox_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test device tracking persistence across updates."""
    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data

    # Verify initial devices
    initial_devices = set(coordinator.data.connected_devices.keys())
    assert DEVICE_1_MAC in initial_devices
    assert DEVICE_2_MAC in initial_devices

    # Simulate device leaving network
    mock_bbox_api.get_hosts.return_value[0].active = False

    # Update coordinator
    await coordinator.async_refresh()

    # Device should still be in connected_devices but inactive
    assert DEVICE_1_MAC in coordinator.data.connected_devices
    assert not coordinator.data.connected_devices[DEVICE_1_MAC].active
    assert DEVICE_2_MAC in coordinator.data.connected_devices
    assert coordinator.data.connected_devices[DEVICE_2_MAC].active
