"""Provides diagnostics for Zeversolar."""

from typing import Any

from zeversolar import ZeverSolarData

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .coordinator import ZeversolarConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ZeversolarConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    data: ZeverSolarData = config_entry.runtime_data.data

    payload: dict[str, Any] = {
        "wifi_enabled": data.wifi_enabled,
        "serial_or_registry_id": data.serial_or_registry_id,
        "registry_key": data.registry_key,
        "hardware_version": data.hardware_version,
        "software_version": data.software_version,
        "reported_datetime": data.reported_datetime,
        "communication_status": data.communication_status.value,
        "num_inverters": data.num_inverters,
        "serial_number": data.serial_number,
        "pac": data.pac,
        "energy_today": data.energy_today,
        "status": data.status.value,
        "meter_status": data.meter_status.value,
    }

    return payload


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ZeversolarConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device entry."""
    coordinator = entry.runtime_data

    updateInterval = (
        None
        if coordinator.update_interval is None
        else coordinator.update_interval.total_seconds()
    )

    return {
        "name": coordinator.name,
        "always_update": coordinator.always_update,
        "last_update_success": coordinator.last_update_success,
        "update_interval": updateInterval,
    }
