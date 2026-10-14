"""Diagnostics support for Twitch."""

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import TwitchConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: TwitchConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "channels": {
            channel_id: asdict(channel)
            for channel_id, channel in entry.runtime_data.data.items()
        },
    }
