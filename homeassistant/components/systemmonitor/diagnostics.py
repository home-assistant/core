"""Diagnostics support for Sensibo."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN_COORDINATORS
from .coordinator import MonitorCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for Sensibo config entry."""
    coordinators: dict[str, MonitorCoordinator] = hass.data[DOMAIN_COORDINATORS]

    diag_data = {}
    for _type, coordinator in coordinators.items():
        diag_data[_type] = {
            "last_update_success": coordinator.last_update_success,
            "last_update": str(coordinator.last_update_success_time),
            "data": str(coordinator.data),
        }

    return {
        "entry": entry.as_dict(),
        "coordinators": diag_data,
    }
