"""Diagnostics support for Ambient PWS."""
from __future__ import annotations

from types import MappingProxyType
from typing import Any

from homeassistant.components.diagnostics import REDACTED
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant, callback

from . import AmbientStation
from .const import CONF_APP_KEY, DOMAIN

CONF_API_KEY_CAMEL = "apiKey"
CONF_APP_KEY_CAMEL = "appKey"
CONF_DEVICE_ID_CAMEL = "deviceId"
CONF_LOCATION = "location"
CONF_MAC_ADDRESS = "mac_address"
CONF_MAC_ADDRESS_CAMEL = "macAddress"
CONF_TZ = "tz"


@callback
def _async_redact_data(data: MappingProxyType | dict) -> dict[str, Any]:
    """Redact sensitive data in a dict."""
    redacted = {**data}

    for key, value in redacted.items():
        if key in (
            CONF_API_KEY,
            CONF_API_KEY_CAMEL,
            CONF_APP_KEY,
            CONF_APP_KEY_CAMEL,
            CONF_DEVICE_ID_CAMEL,
            CONF_LOCATION,
            CONF_MAC_ADDRESS,
            CONF_MAC_ADDRESS_CAMEL,
            CONF_TZ,
        ):
            redacted[key] = REDACTED
        elif isinstance(value, dict):
            redacted[key] = _async_redact_data(value)
        elif isinstance(value, list):
            redacted[key] = [_async_redact_data(item) for item in value]

    return redacted


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    ambient: AmbientStation = hass.data[DOMAIN][entry.entry_id]

    return {
        "entry": {
            "title": entry.title,
            "data": _async_redact_data(entry.data),
        },
        "stations": _async_redact_data(ambient.stations),
    }
