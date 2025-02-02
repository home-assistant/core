"""Diagnostics for the Swiss public transport integration."""

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import SwissPublicTransportConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SwissPublicTransportConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    return {
        "entry_data": dict(entry.data),
        "data": entry.runtime_data.data,
        "stats": {
            key: asdict(stats) for key, stats in entry.runtime_data.stats.items()
        },
    }
