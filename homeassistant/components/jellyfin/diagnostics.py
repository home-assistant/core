"""Diagnostics support for Jellyfin."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from . import JellyfinConfigEntry

TO_REDACT = {CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: JellyfinConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(entry.data, TO_REDACT),
        },
        "server": {
            "id": coordinator.server_id,
            "name": coordinator.server_name,
            "version": coordinator.server_version,
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
            for session_id, session_data in coordinator.data.items()
        ],
    }
