"""Diagnostics support for Home Connect Diagnostics."""

from __future__ import annotations

from typing import Any

from homeconnect.api import HomeConnectAppliance

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from . import HomeConnectConfigEntry, _get_appliance_by_device_id
from .api import HomeConnectDevice


def _generate_appliance_diagnostics(appliance: HomeConnectAppliance) -> dict[str, Any]:
    return {
        "status": appliance.status,
        "programs": appliance.get_programs_available(),
    }


def _generate_entry_diagnostics(
    devices: list[HomeConnectDevice],
) -> dict[str, dict[str, Any]]:
    return {
        device.appliance.haId: _generate_appliance_diagnostics(device.appliance)
        for device in devices
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HomeConnectConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return await hass.async_add_executor_job(
        _generate_entry_diagnostics, entry.runtime_data.devices
    )


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    appliance = _get_appliance_by_device_id(hass, device.id, entry)
    return await hass.async_add_executor_job(_generate_appliance_diagnostics, appliance)
