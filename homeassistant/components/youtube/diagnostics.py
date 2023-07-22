"""Diagnostics support for YouTube."""
from __future__ import annotations

import json
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import COORDINATOR, DOMAIN
from .coordinator import YouTubeDataUpdateCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: YouTubeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        COORDINATOR
    ]
    sensor_data = {}
    for channel_id, channel_data in coordinator.data.items():
        obj = {}
        if channel_data.latest_video is not None:
            obj = json.loads(channel_data.latest_video.json())
            obj.get("nullable_snippet", {"description": ""}).pop("description")
        channel_obj = json.loads(channel_data.channel.json())
        channel_obj.get("nullable_snippet", {"description": ""}).pop("description")
        sensor_data[channel_id] = {
            "channel": channel_obj,
            "latest_video": obj,
        }
    return sensor_data
