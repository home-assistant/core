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
    return {
        "info": data.info.dict(),
        "device": data.device.dict(),
        "state": data.coordinator.data.dict(),
    }
