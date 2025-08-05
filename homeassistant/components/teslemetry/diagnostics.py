"""Provides diagnostics for Teslemetry."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import TeslemetryConfigEntry

VEHICLE_REDACT = [
    "id",
    "user_id",
    "vehicle_id",
    "vin",
    "tokens",
    "id_s",
    "drive_state_active_route_latitude",
    "drive_state_active_route_longitude",
    "drive_state_latitude",
    "drive_state_longitude",
    "drive_state_native_latitude",
    "drive_state_native_longitude",
]

ENERGY_LIVE_REDACT = ["vin"]
ENERGY_INFO_REDACT = ["installation_date"]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: TeslemetryConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    vehicles = [
        {
            "data": async_redact_data(x.coordinator.data, VEHICLE_REDACT),
            "stream": {
                "config": x.stream_vehicle.config,
            },
        }
        for x in entry.runtime_data.vehicles
    ]
    energysites = [
        {
            "live": async_redact_data(x.live_coordinator.data, ENERGY_LIVE_REDACT)
            if x.live_coordinator
            else None,
            "info": async_redact_data(x.info_coordinator.data, ENERGY_INFO_REDACT),
            "history": x.history_coordinator.data if x.history_coordinator else None,
        }
        for x in entry.runtime_data.energysites
    ]

    # Return only the relevant children
    return {
        "vehicles": vehicles,
        "energysites": energysites,
        "scopes": entry.runtime_data.scopes,
    }
