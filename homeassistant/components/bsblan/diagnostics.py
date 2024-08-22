"""Diagnostics support for BSBLan."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from . import HomeAssistantBSBLANData


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data: HomeAssistantBSBLANData = hass.data[DOMAIN][entry.entry_id]
    return {
        "info": data.info.to_dict(),
        "device": data.device.to_dict(),
        "state": data.coordinator.data.to_dict(),
    }
