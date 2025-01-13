"""Diagnostics support for Elgato."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import ElgatoConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ElgatoConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return {
        "info": coordinator.data.info.to_dict(),
        "state": coordinator.data.state.to_dict(),
    }
