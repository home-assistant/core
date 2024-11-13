"""Diagnostics support for Home Connect Diagnostics."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import (
    DOMAIN,
)

async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = {}
    for hc_api in hass.data[DOMAIN].values():
        for device in hc_api.devices:
            data[device.device_id] = device.appliance.status
    return data
