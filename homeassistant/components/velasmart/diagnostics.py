"""Diagnostics support for the VelaSmart integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    return {
        "config_entry": {k: v for k, v in entry.data.items() if k != CONF_PASSWORD},
        "devices": coordinator.data,
    }
