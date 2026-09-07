"""Diagnostics support for YouTube."""

from typing import Any

from homeassistant.core import HomeAssistant

from .const import (
    ATTR_DESCRIPTION,
    ATTR_LATEST_SHORT,
    ATTR_LATEST_VIDEO,
    ATTR_LATEST_VIDEO_NON_SHORT,
    CONF_CHANNEL_ID,
)
from .coordinator import YouTubeConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: YouTubeConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    sensor_data: dict[str, Any] = {}
    for coordinator in entry.runtime_data.values():
        channel_id = coordinator.subentry.data[CONF_CHANNEL_ID]
        if coordinator.data is None:
            # The channel could not be fetched and has no data.
            sensor_data[channel_id] = None
            continue
        channel_copy = dict(coordinator.data)
        # Strip verbose description field from all video entries.
        for attr in (
            ATTR_LATEST_VIDEO,
            ATTR_LATEST_SHORT,
            ATTR_LATEST_VIDEO_NON_SHORT,
        ):
            if video := channel_copy.get(attr):
                channel_copy[attr] = {
                    key: value
                    for key, value in video.items()
                    if key != ATTR_DESCRIPTION
                }
        sensor_data[channel_id] = channel_copy
    return sensor_data
