"""Diagnostics support for Roku."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import RokuDataUpdateCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: RokuDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    return {
        "config_entry": {
            **config_entry.data,
        },
        "coordinator": coordinator.data.as_dict(),
    }
