"""Diagnostics support for Android TV Remote."""
from __future__ import annotations

from typing import Any

from androidtvremote2 import AndroidTVRemote

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.core import HomeAssistant

from .const import DOMAIN

TO_REDACT = {CONF_HOST, CONF_MAC}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    api: AndroidTVRemote = hass.data[DOMAIN].pop(entry.entry_id)
    return async_redact_data(
        {
            "api_device_info": api.device_info,
            "config_entry_data": entry.data,
        },
        TO_REDACT,
    )
