"""Test the LibreHardwareMonitor coordinator."""

from unittest.mock import AsyncMock, patch

from librehardwaremonitor_api import (
    LibreHardwareMonitorConnectionError,
    LibreHardwareMonitorNoDevicesError,
)
from librehardwaremonitor_api.model import LibreHardwareMonitorData
import pytest

from homeassistant.components.librehardwaremonitor import (
    LibreHardwareMonitorCoordinator,
)
from homeassistant.components.librehardwaremonitor.const import DOMAIN
from homeassistant.const import CONF_DEVICES
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import init_integration


async def test_connection_error_raises_update_failed(
    hass: HomeAssistant, mock_lhm_client: AsyncMock
) -> None:
    """Test that UpdateFailed error is raised if connection to LibreHardwareMonitor fails."""
    mock_entry = await init_integration(hass)
    mock_lhm_client.get_data.side_effect = LibreHardwareMonitorConnectionError()

    coordinator = LibreHardwareMonitorCoordinator(hass, mock_entry)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_no_devices_error_raises_update_failed(
    hass: HomeAssistant, mock_lhm_client: AsyncMock
) -> None:
    """Test that NoDevices error is raised if LibreHardwareMonitor does not return sensor data."""
    mock_entry = await init_integration(hass)
    mock_lhm_client.get_data.side_effect = LibreHardwareMonitorNoDevicesError()

    coordinator = LibreHardwareMonitorCoordinator(hass, mock_entry)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_refresh_updates_data(
    hass: HomeAssistant, mock_lhm_client: AsyncMock
) -> None:
    """Test that sensor data is updated with LibreHardwareMonitor data."""
    mock_entry = await init_integration(hass)
    coordinator = LibreHardwareMonitorCoordinator(hass, mock_entry)

    await coordinator._async_refresh()

    assert coordinator.data
    assert len(coordinator.data.sensor_data) == 25
    assert all(
        sensor.device_type != "UNKNOWN"
        for sensor in coordinator.data.sensor_data.values()
    )

    sensor_data = coordinator.data.sensor_data.get("amdcpu-0-power-0")
    assert sensor_data
    assert sensor_data.name == "Package Power"
    assert sensor_data.value == "31,0"
    assert sensor_data.min == "30,7"
    assert sensor_data.max == "46,6"
    assert sensor_data.unit == "W"
    assert sensor_data.device_name == "AMD Ryzen 7 7800X3D"
    assert sensor_data.device_type == "CPU"
    assert sensor_data.sensor_id == "amdcpu-0-power-0"


async def test_orphaned_devices_are_removed(
    hass: HomeAssistant, mock_lhm_client: AsyncMock
) -> None:
    """Test that devices in HA that do not receive updates are removed."""
    mock_entry = await init_integration(hass)
    coordinator = LibreHardwareMonitorCoordinator(hass, mock_entry)

    await coordinator._async_refresh()

    mock_lhm_client.get_data.return_value = LibreHardwareMonitorData(
        main_device_names=["AMD Ryzen 7 7800X3D", "NVIDIA GeForce RTX 4080 SUPER"],
        sensor_data=mock_lhm_client.get_data.return_value.sensor_data,
    )

    device_registry = dr.async_get(hass)
    orphaned_device = device_registry.async_get_or_create(
        config_entry_id=mock_entry.entry_id,
        identifiers={(DOMAIN, "MSI MAG B650M MORTAR WIFI (MS-7D76)")},
    )

    with patch.object(
        device_registry,
        "async_remove_device",
        wraps=device_registry.async_update_device,
    ) as mock_remove:
        await coordinator._async_refresh()
        mock_remove.assert_called_once_with(orphaned_device.id)

    assert mock_entry.options[CONF_DEVICES] == [
        "AMD Ryzen 7 7800X3D",
        "NVIDIA GeForce RTX 4080 SUPER",
    ]


async def test_new_devices_are_added_and_integration_reloaded(
    hass: HomeAssistant, mock_lhm_client: AsyncMock
) -> None:
    """Test that devices not yet in HA are added to the integration."""
    mock_entry = await init_integration(hass)
    coordinator = LibreHardwareMonitorCoordinator(hass, mock_entry)

    await coordinator._async_refresh()

    mock_lhm_client.get_data.return_value = LibreHardwareMonitorData(
        main_device_names=[
            *mock_lhm_client.get_data.return_value.main_device_names,
            "Generic Memory",
        ],
        sensor_data=mock_lhm_client.get_data.return_value.sensor_data,
    )

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_schedule_reload"
    ) as async_schedule_reload:
        await coordinator._async_refresh()
        async_schedule_reload.assert_called_with(mock_entry.entry_id)

    assert mock_entry.options[CONF_DEVICES] == [
        "MSI MAG B650M MORTAR WIFI (MS-7D76)",
        "AMD Ryzen 7 7800X3D",
        "NVIDIA GeForce RTX 4080 SUPER",
        "Generic Memory",
    ]
