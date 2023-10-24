"""Diagnostics support for Honeywell."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import HoneywellData
from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    Honeywell: HoneywellData = hass.data[DOMAIN][config_entry.entry_id]
    diagnostics_data = {}

    for device, module in Honeywell.devices.items():
        diagnostics_data.update(
            {
                f"Device {device}": {
                    "UI Data": module.raw_ui_data,
                    "Fan Data": module.raw_fan_data,
                    "DR Data": module.raw_dr_data,
                }
            }
        )

    return diagnostics_data
