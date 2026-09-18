"""Diagnostics for HDFury Integration."""

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import HDFuryConfigEntry, HDFuryCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HDFuryConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: HDFuryCoordinator = entry.runtime_data

    return {
        "board": coordinator.data.board,
        "info": coordinator.data.info,
        "config": coordinator.data.config,
    }
