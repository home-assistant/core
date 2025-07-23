"""Test the LibreHardwareMonitor coordinator."""

from unittest.mock import AsyncMock

from librehardwaremonitor_api import (
    LibreHardwareMonitorConnectionError,
    LibreHardwareMonitorNoDevicesError,
)
import pytest

from homeassistant.components.libre_hardware_monitor import (
    LibreHardwareMonitorCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


async def test_connection_error_raises_update_failed(
    hass: HomeAssistant, mock_lhm_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test that UpdateFailed error is raised if connection to LibreHardwareMonitor fails."""
    mock_config_entry.add_to_hass(hass)
    mock_lhm_client.get_data.side_effect = LibreHardwareMonitorConnectionError()

    coordinator = LibreHardwareMonitorCoordinator(hass, mock_config_entry)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_no_devices_error_raises_update_failed(
    hass: HomeAssistant, mock_lhm_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test that UpdateFailed error is raised if LibreHardwareMonitor does not return sensor data."""
    mock_config_entry.add_to_hass(hass)
    mock_lhm_client.get_data.side_effect = LibreHardwareMonitorNoDevicesError()

    coordinator = LibreHardwareMonitorCoordinator(hass, mock_config_entry)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
