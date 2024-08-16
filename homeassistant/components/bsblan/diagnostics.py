"""Diagnostics support for BSBLan."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import HomeAssistantBSBLANData
from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data: HomeAssistantBSBLANData = hass.data[DOMAIN][entry.entry_id]

    # Helper function to safely get dict from potentially async methods
    async def safe_to_dict(obj):
        if callable(getattr(obj, "to_dict", None)):
            result = obj.to_dict()
            return await result if hasattr(result, "__await__") else result
        return obj

    return {
        "info": await safe_to_dict(data.info),
        "device": await safe_to_dict(data.device),
        "coordinator_data": {
            "state": await safe_to_dict(data.coordinator.data["state"]),
            "sensor": await safe_to_dict(data.coordinator.data["sensor"]),
        },
        "static": await safe_to_dict(data.static),
    }
