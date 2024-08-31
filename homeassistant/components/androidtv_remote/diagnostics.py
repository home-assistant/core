"""Diagnostics support for Android TV Remote."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.core import HomeAssistant

from . import AndroidTVRemoteConfigEntry

TO_REDACT = {CONF_HOST, CONF_MAC}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AndroidTVRemoteConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    api = entry.runtime_data
    return async_redact_data(
        {
            "api_device_info": api.device_info,
            "config_entry_data": entry.data,
        },
        TO_REDACT,
    )
