"""Diagnostics support for YouTube."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import ATTR_DESCRIPTION, ATTR_LATEST_VIDEO, COORDINATOR, DOMAIN
from .coordinator import YouTubeDataUpdateCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: YouTubeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        COORDINATOR
    ]
    sensor_data: dict[str, Any] = {}
    for channel_id, channel_data in coordinator.data.items():
        channel_copy = dict(channel_data)
        if latest_video := channel_copy.get(ATTR_LATEST_VIDEO):
            channel_copy[ATTR_LATEST_VIDEO] = {
                key: value
                for key, value in latest_video.items()
                if key != ATTR_DESCRIPTION
            }
        sensor_data[channel_id] = channel_copy
    return sensor_data
