"""Diagnostics for the Nina integration."""

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import NinaConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NinaConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    return {
        "entry_data": dict(entry.data),
        "data": entry.runtime_data.data,
    }
