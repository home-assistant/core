"""Provides diagnostics for Tessie."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import TessieConfigEntry

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
ENERGY_INFO_REDACT = ["installation_date", "serial_number"]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: TessieConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    vehicles = [
        {
            "data": async_redact_data(x.data_coordinator.data, VEHICLE_REDACT),
            # Battery diag will go here when implemented
        }
        for x in entry.runtime_data.vehicles
    ]
    energysites = [
        {
            "live": async_redact_data(x.live_coordinator.data, ENERGY_LIVE_REDACT)
            if x.live_coordinator
            else None,
            "info": async_redact_data(x.info_coordinator.data, ENERGY_INFO_REDACT),
        }
        for x in entry.runtime_data.energysites
    ]

    # Return only the relevant children
    return {
        "vehicles": vehicles,
        "energysites": energysites,
    }
