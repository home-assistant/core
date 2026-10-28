"""Diagnostics support for Logitech Harmony Hub."""

from typing import Any

from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .data import HarmonyConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HarmonyConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data
    device_info = data.device_info(DOMAIN)
    activity_id, activity_name = data.current_activity
    return {
        "options": dict(entry.options),
        "available": data.available,
        "model": device_info.get("model"),
        "sw_version": device_info.get("sw_version"),
        "current_activity": {"id": activity_id, "name": activity_name},
        "config": data.json_config,
    }
