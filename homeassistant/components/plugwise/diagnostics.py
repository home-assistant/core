"""Diagnostics support for Plugwise."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import PlugwiseDataUpdateCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: PlugwiseDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    return {
        "gateway": coordinator.data.gateway,
        "devices": coordinator.data.devices,
    }
