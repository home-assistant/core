"""Diagnostics support for Home Connect Diagnostics."""

from __future__ import annotations

from typing import Any

from homeconnect.api import HomeConnectAppliance

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from . import _get_appliance_by_device_id
from .api import HomeConnectDevice
from .const import DOMAIN


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
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return await hass.async_add_executor_job(
        _generate_entry_diagnostics, hass.data[DOMAIN][config_entry.entry_id].devices
    )


async def async_get_device_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    appliance = _get_appliance_by_device_id(hass, device.id)
    return await hass.async_add_executor_job(_generate_appliance_diagnostics, appliance)
