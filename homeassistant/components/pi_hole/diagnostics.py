"""Diagnostics support for the Pi-hole integration."""
from __future__ import annotations

from typing import Any

from hole import Hole

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from .const import DATA_KEY_API, DOMAIN

TO_REDACT = {CONF_API_KEY}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    api: Hole = hass.data[DOMAIN][entry.entry_id][DATA_KEY_API]

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "data": api.data,
        "versions": api.versions,
    }
