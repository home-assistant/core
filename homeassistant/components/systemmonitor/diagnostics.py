"""Diagnostics support for Sensibo."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import SystemMonitorConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SystemMonitorConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for Sensibo config entry."""
    coordinator = entry.runtime_data.coordinator

    diag_data = {
        "last_update_success": coordinator.last_update_success,
        "last_update": str(coordinator.last_update_success_time),
        "data": coordinator.data.as_dict(),
    }

    return {
        "entry": entry.as_dict(),
        "coordinators": diag_data,
    }
