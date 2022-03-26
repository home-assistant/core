"""Diagnostics support for Ambient PWS."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LOCATION
from homeassistant.core import HomeAssistant

from . import AmbientStation
from .const import CONF_APP_KEY, DOMAIN

CONF_API_KEY_CAMEL = "apiKey"
CONF_APP_KEY_CAMEL = "appKey"
CONF_DEVICE_ID_CAMEL = "deviceId"
CONF_MAC_ADDRESS = "mac_address"
CONF_MAC_ADDRESS_CAMEL = "macAddress"
CONF_TZ = "tz"

TO_REDACT = {
    CONF_API_KEY,
    CONF_API_KEY_CAMEL,
    CONF_APP_KEY,
    CONF_APP_KEY_CAMEL,
    CONF_DEVICE_ID_CAMEL,
    CONF_LOCATION,
    CONF_MAC_ADDRESS,
    CONF_MAC_ADDRESS_CAMEL,
    CONF_TZ,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    ambient: AmbientStation = hass.data[DOMAIN][entry.entry_id]

    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(entry.data, TO_REDACT),
        },
        "stations": async_redact_data(ambient.stations, TO_REDACT),
    }
