"""Diagnostics support for Home Connect Diagnostics."""

from __future__ import annotations

from typing import Any

from homeconnect.api import HomeConnectAppliance

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from . import _get_appliance_by_device_id
from .const import DOMAIN


async def _async_generate_appliance_diagnostics(
    hass: HomeAssistant, appliance: HomeConnectAppliance
) -> dict[str, Any]:
    return {
        "status": appliance.status,
        "programs": await hass.async_add_executor_job(appliance.get_programs_available),
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        device.appliance.haId: await _async_generate_appliance_diagnostics(
            hass, device.appliance
        )
        for device in hass.data[DOMAIN][config_entry.entry_id].devices
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    appliance = _get_appliance_by_device_id(hass, device.id)
    return await _async_generate_appliance_diagnostics(hass, appliance)
