"""Test the LibreHardwareMonitor coordinator."""

from unittest.mock import AsyncMock

from librehardwaremonitor_api import LibreHardwareMonitorConnectionError
import pytest

from homeassistant.components.librehardwaremonitor import (
    LibreHardwareMonitorCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import CONFIGURED_DEVICES, init_integration


async def test_connection_error_raises_update_failed(
    hass: HomeAssistant, mock_lhm_client: AsyncMock
) -> None:
    """Test that UpdateFailed error is raised if connection to LibreHardwareMonitor fails."""
    mock_entry = await init_integration(hass)
    mock_lhm_client.get_data_json.side_effect = LibreHardwareMonitorConnectionError()

    coordinator = LibreHardwareMonitorCoordinator(hass, mock_entry)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_refresh_updates_data_for_configured_devices(
    hass: HomeAssistant, mock_lhm_client: AsyncMock
) -> None:
    """Test that sensor data is parsed from LibreHardwareMonitor data only for configured devices."""
    mock_entry = await init_integration(hass)
    coordinator = LibreHardwareMonitorCoordinator(hass, mock_entry)

    await coordinator._async_refresh()

    assert coordinator.data
    assert len(coordinator.data) == 109
    assert all(
        sensor.device_name in CONFIGURED_DEVICES for sensor in coordinator.data.values()
    )
    assert all(sensor.device_type != "UNKNOWN" for sensor in coordinator.data.values())

    sensor_data = coordinator.data.get("amdcpu-0-voltage-12")
    assert sensor_data
    assert sensor_data.name == "Core #7 VID Voltage"
    assert sensor_data.value == "0,925"
    assert sensor_data.min == "0,369"
    assert sensor_data.max == "1,350"
    assert sensor_data.unit == "V"
    assert sensor_data.device_name == "AMD Ryzen 7 7800X3D"
    assert sensor_data.device_type == "CPU"
    assert sensor_data.sensor_id == "amdcpu-0-voltage-12"
