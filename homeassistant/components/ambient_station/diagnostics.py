"""Diagnostics support for Ambient PWS."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LOCATION, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant

from . import AmbientStation
from .const import CONF_APP_KEY, DOMAIN

CONF_API_KEY_CAMEL = "apiKey"
CONF_APP_KEY_CAMEL = "appKey"
CONF_DEVICE_ID_CAMEL = "deviceId"
CONF_MAC_ADDRESS = "mac_address"
CONF_MAC_ADDRESS_CAMEL = "macAddress"
CONF_TITLE = "title"
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
    # Config entry title and unique ID may contain sensitive data:
    CONF_TITLE,
    CONF_UNIQUE_ID,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    ambient: AmbientStation = hass.data[DOMAIN][entry.entry_id]

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "stations": async_redact_data(ambient.stations, TO_REDACT),
    }
