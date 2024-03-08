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
        channel_data.get(ATTR_LATEST_VIDEO, {}).pop(ATTR_DESCRIPTION)
        sensor_data[channel_id] = channel_data
    return sensor_data
