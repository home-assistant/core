"""Diagnostics for HDFury Integration."""

from typing import Any

from homeassistant.core import HomeAssistant

from . import HDFuryConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HDFuryConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime_data = entry.runtime_data

    return {
        "board": runtime_data.board,
        "info": runtime_data.info_coordinator.data,
        "config": runtime_data.config_coordinator.data,
    }
