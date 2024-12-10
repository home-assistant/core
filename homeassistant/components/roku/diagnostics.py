"""Diagnostics support for Roku."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import RokuConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: RokuConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    return {
        "entry": {
            "data": {
                **entry.data,
            },
            "unique_id": entry.unique_id,
        },
        "data": coordinator.data.as_dict(),
    }
