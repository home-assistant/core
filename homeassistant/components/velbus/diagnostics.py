"""Diagnostics support for Velbus."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    cntrl = hass.data[DOMAIN][entry.entry_id]["cntrl"]
    diag: dict[str, Any] = {"entry": entry.as_dict(), "modules": []}
    for addr, mod in cntrl.get_modules().items():
        diag["modules"].append(
            {
                "type": mod.get_type_name(),
                "address": addr,
                "name": mod.get_name(),
                "sw_version": mod.get_sw_version(),
                "is_loaded": mod.is_loaded(),
                "channels": mod.get_channels(),
            }
        )

    return diag
