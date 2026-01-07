"""Diagnostics support for Victron Energy integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN

TO_REDACT = ["token", "username", "password", "ha_device_id"]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    manager = hass.data.get(DOMAIN, {}).get(entry.entry_id)

    data = {}
    if manager:
        # Provide basic manager status without accessing private members
        data = {
            "connection_state": "connected" if manager.client else "disconnected",
            "manager_available": True,
        }

    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "data": data,
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device: dr.DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device entry."""
    return {
        "device_info": {
            "identifiers": list(device.identifiers),
            "name": device.name,
            "manufacturer": device.manufacturer,
            "model": device.model,
        },
        "note": "Device details simplified to avoid private member access",
    }
