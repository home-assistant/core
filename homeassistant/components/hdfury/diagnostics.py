"""Diagnostics for HDFury Integration."""

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .coordinator import HDFuryCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: HDFuryCoordinator = entry.runtime_data

    return {
        "board": coordinator.data.board,
        "info": coordinator.data.info,
        "config": coordinator.data.config,
    }
