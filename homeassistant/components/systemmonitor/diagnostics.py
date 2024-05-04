"""Diagnostics support for Sensibo."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN_COORDINATOR
from .coordinator import SystemMonitorCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for Sensibo config entry."""
    coordinator: SystemMonitorCoordinator = hass.data[DOMAIN_COORDINATOR]

    diag_data = {
        "last_update_success": coordinator.last_update_success,
        "last_update": str(coordinator.last_update_success_time),
        "data": coordinator.data.as_dict(),
    }

    return {
        "entry": entry.as_dict(),
        "coordinators": diag_data,
    }
