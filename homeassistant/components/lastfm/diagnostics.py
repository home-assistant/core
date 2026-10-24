"""Diagnostics support for LastFM."""

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import LastFMConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: LastFMConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "users": [asdict(user_data) for user_data in entry.runtime_data.data.values()],
    }
