"""Diagnostics support for Honeywell."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import HoneywellConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: HoneywellConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    honeywell = config_entry.runtime_data

    return {
        f"Device {device}": {
            "UI Data": module.raw_ui_data,
            "Fan Data": module.raw_fan_data,
            "DR Data": module.raw_dr_data,
        }
        for device, module in honeywell.devices.items()
    }
