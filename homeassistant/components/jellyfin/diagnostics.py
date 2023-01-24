"""Diagnostics support for Jellyfin."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .models import JellyfinData

TO_REDACT = {CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data: JellyfinData = hass.data[DOMAIN][entry.entry_id]
    sessions = data.coordinators["sessions"]

    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(entry.data, TO_REDACT),
        },
        "server": {
            "id": sessions.server_id,
            "name": sessions.server_name,
            "version": sessions.server_version,
        },
        "sessions": [
            {
                "id": session_id,
                "user_id": session_data.get("UserId"),
                "device_id": session_data.get("DeviceId"),
                "device_name": session_data.get("DeviceName"),
                "client_name": session_data.get("Client"),
                "client_version": session_data.get("ApplicationVersion"),
                "capabilities": session_data.get("Capabilities"),
                "now_playing": session_data.get("NowPlayingItem"),
                "play_state": session_data.get("PlayState"),
            }
            for session_id, session_data in sessions.data.items()
        ],
    }
