"""Diagnostics support for LG webOS Smart TV."""

from __future__ import annotations

from typing import Any

from aiowebostv import WebOsClient

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_CLIENT_SECRET, CONF_HOST, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant

from . import WebOsTvConfigEntry

TO_REDACT = {
    CONF_CLIENT_SECRET,
    CONF_UNIQUE_ID,
    CONF_HOST,
    "device_id",
    "deviceUUID",
    "icon",
    "largeIcon",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: WebOsTvConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    client: WebOsClient = entry.runtime_data

    client_data = {
        "is_registered": client.is_registered(),
        "is_connected": client.is_connected(),
        "current_app_id": client.current_app_id,
        "current_channel": client.current_channel,
        "apps": client.apps,
        "inputs": client.inputs,
        "system_info": client.system_info,
        "software_info": client.software_info,
        "hello_info": client.hello_info,
        "sound_output": client.sound_output,
        "is_on": client.is_on,
    }

    return async_redact_data(
        {
            "entry": entry.as_dict(),
            "client": client_data,
        },
        TO_REDACT,
    )
