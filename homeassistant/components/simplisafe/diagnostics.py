"""Diagnostics support for SimpliSafe."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant

from . import SimpliSafe
from .const import DOMAIN

CONF_SERIAL = "serial"
CONF_SYSTEM_ID = "system_id"
CONF_WIFI_SSID = "wifi_ssid"

TO_REDACT = {
    CONF_ADDRESS,
    CONF_SERIAL,
    CONF_SYSTEM_ID,
    CONF_WIFI_SSID,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    simplisafe: SimpliSafe = hass.data[DOMAIN][entry.entry_id]

    return async_redact_data(
        {
            "entry": {
                "options": dict(entry.options),
            },
            "systems": [system.as_dict() for system in simplisafe.systems.values()],
        },
        TO_REDACT,
    )
