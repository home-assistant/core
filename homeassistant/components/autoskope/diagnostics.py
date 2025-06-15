"""Diagnostics support for Autoskope."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .coordinator import AutoskopeConfigEntry, AutoskopeDataUpdateCoordinator

TO_REDACT = {
    CONF_PASSWORD,
    CONF_USERNAME,
    "imei",
    "id",
    "carid",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AutoskopeConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: AutoskopeDataUpdateCoordinator = entry.runtime_data.coordinator

    vehicles_data = {}
    if coordinator.data:
        for vehicle_id, vehicle in coordinator.data.items():
            vehicles_data[vehicle_id] = {
                "name": vehicle.name,
                "model": vehicle.model,
                "battery_voltage": vehicle.battery_voltage,
                "external_voltage": vehicle.external_voltage,
                "gps_quality": vehicle.gps_quality,
                "has_position": vehicle.position is not None,
                "position": {
                    "speed": vehicle.position.speed if vehicle.position else None,
                    "park_mode": vehicle.position.park_mode
                    if vehicle.position
                    else None,
                    "has_coordinates": bool(vehicle.position),
                },
            }

    return async_redact_data(
        {
            "entry": {
                "title": entry.title,
                "data": dict(entry.data),
            },
            "coordinator": {
                "last_update_success": coordinator.last_update_success,
                "update_interval": str(coordinator.update_interval),
            },
            "vehicles": vehicles_data,
            "vehicles_count": len(coordinator.data) if coordinator.data else 0,
        },
        TO_REDACT,
    )
