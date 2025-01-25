"""Diagnostics support for Home Connect Diagnostics."""

from __future__ import annotations

from typing import Any

from homeconnect.api import HomeConnectAppliance, HomeConnectError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from . import HomeConnectConfigEntry, _get_appliance
from .api import HomeConnectDevice


def _generate_appliance_diagnostics(appliance: HomeConnectAppliance) -> dict[str, Any]:
    try:
        programs = appliance.get_programs_available()
    except HomeConnectError:
        programs = None
    return {
        "connected": appliance.connected,
        "status": appliance.status,
        "programs": programs,
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
    hass: HomeAssistant, entry: HomeConnectConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    appliance = _get_appliance(hass, device_entry=device, entry=entry)
    return await hass.async_add_executor_job(_generate_appliance_diagnostics, appliance)
