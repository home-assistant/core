"""Diagnostics support for lutron_caseta."""
from __future__ import annotations

from typing import Any

from pylutron_caseta.smartbridge import Smartbridge

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import BRIDGE_LEAP, DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    bridge: Smartbridge = hass.data[DOMAIN][entry.entry_id][BRIDGE_LEAP]
    return {
        "entry": {
            "title": entry.title,
            "data": dict(entry.data),
        },
        "data": {
            "devices": bridge.devices,
            "buttons": bridge.buttons,
            "scenes": bridge.scenes,
            "occupancy_groups": bridge.occupancy_groups,
            "areas": bridge.areas,
        },
    }
