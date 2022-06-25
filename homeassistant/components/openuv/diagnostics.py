"""Diagnostics support for OpenUV."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from . import OpenUV
from .const import DOMAIN

CONF_COORDINATES = "coordinates"

TO_REDACT = {
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    openuv: OpenUV = hass.data[DOMAIN][entry.entry_id]

    return {
        "entry": {
            "data": async_redact_data(entry.data, TO_REDACT),
            "options": async_redact_data(entry.options, TO_REDACT),
        },
        "data": async_redact_data(openuv.data, TO_REDACT),
    }
