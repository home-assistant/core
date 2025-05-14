"""Diagnostics support for everHome."""

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import EcoTrackerConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: EcoTrackerConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    return {
        "entry_data": entry.data,
        "data": entry.runtime_data.data.to_dict(),
    }
