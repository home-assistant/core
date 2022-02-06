"""Diagnostics support for the Mazda integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics.util import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DATA_COORDINATOR, DOMAIN

TO_REDACT_INFO = [CONF_EMAIL, CONF_PASSWORD]
TO_REDACT_DATA = ["vin", "id", "latitude", "longitude"]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]

    diagnostics_data = {
        "info": async_redact_data(config_entry.data, TO_REDACT_INFO),
        "data": [
            async_redact_data(vehicle, TO_REDACT_DATA) for vehicle in coordinator.data
        ],
    }

    return diagnostics_data


async def async_get_device_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]

    vin = next(iter(device.identifiers))[1]

    target_vehicle = None
    for vehicle in coordinator.data:
        if vehicle["vin"] == vin:
            target_vehicle = vehicle
            break

    if target_vehicle is None:
        raise HomeAssistantError("Vehicle not found")

    diagnostics_data = {
        "info": async_redact_data(config_entry.data, TO_REDACT_INFO),
        "data": async_redact_data(target_vehicle, TO_REDACT_DATA),
    }

    return diagnostics_data
