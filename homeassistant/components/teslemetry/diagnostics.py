"""Provides diagnostics for Teslemetry."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

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

ENERGY_REDACT = ["vin"]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    vehicles = [
        x.coordinator.data for x in hass.data[DOMAIN][config_entry.entry_id].vehicles
    ]
    energysites = [
        x.coordinator.data for x in hass.data[DOMAIN][config_entry.entry_id].energysites
    ]

    # Return only the relevant children
    return {
        "vehicles": async_redact_data(vehicles, VEHICLE_REDACT),
        "energysites": async_redact_data(energysites, ENERGY_REDACT),
    }
