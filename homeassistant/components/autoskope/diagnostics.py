"""Diagnostics support for Autoskope."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import AutoskopeDataUpdateCoordinator
from .models import AutoskopeConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AutoskopeConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    coordinator: AutoskopeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    return {
        "entry": {
            "entry_id": entry.entry_id,
            "title": entry.title,
        },
        "vehicles": [
            {
                "id": vehicle.id,
                "name": vehicle.name,
                "latitude": vehicle.position.latitude if vehicle.position else None,
                "longitude": vehicle.position.longitude if vehicle.position else None,
                "speed": vehicle.position.speed if vehicle.position else None,
                "timestamp": vehicle.position.timestamp if vehicle.position else None,
                "park_mode": vehicle.position.park_mode if vehicle.position else None,
                "battery_voltage": vehicle.battery_voltage,
                "external_voltage": vehicle.external_voltage,
            }
            for vehicle in (coordinator.data.values() if coordinator.data else [])
        ],
        "coordinator_status": {
            "last_update_success": coordinator.last_update_success,
        },
    }
