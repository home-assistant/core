"""Diagnostics support for Home Connect Diagnostics."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        device.appliance.haId: {
            "status": device.appliance.status,
            "programs": await hass.async_add_executor_job(
                device.appliance.get_programs_available
            ),
        }
        for device in hass.data[DOMAIN][config_entry.entry_id].devices
    }
