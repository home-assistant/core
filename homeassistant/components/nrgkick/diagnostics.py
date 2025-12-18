"""Diagnostics support for NRGkick."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import NRGkickConfigEntry, NRGkickDataUpdateCoordinator


async def async_get_config_entry_diagnostics(
    _hass: HomeAssistant,
    entry: NRGkickConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: NRGkickDataUpdateCoordinator = entry.runtime_data

    return {
        "entry": {
            "title": entry.title,
            "unique_id": entry.unique_id,
        },
        "config": {
            "host": entry.data.get("host", "unknown"),
            "has_username": entry.data.get("username") is not None,
            "has_password": entry.data.get("password") is not None,
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "update_interval": (
                coordinator.update_interval.total_seconds()
                if coordinator.update_interval is not None
                else None
            ),
        },
        "data": coordinator.data,
    }
