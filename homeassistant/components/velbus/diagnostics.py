"""Diagnostics support for Velbus."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict:
    """Return diagnostics for a config entry."""
    cntrl = hass.data[DOMAIN][entry.entry_id]["cntrl"]
    return {"entry": entry.as_dict(), "modules": cntrl.get_modules()}
