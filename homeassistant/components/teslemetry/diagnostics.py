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
    "active_route_latitude",
    "active_route_longitude",
    "latitude",
    "longitude",
    "native_latitude",
    "native_longitude",
]

ENERGY_REDACT = ["din"]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    vehicles = hass.data[DOMAIN][config_entry.entry_id].vehicles.map(
        lambda x: x.coordinator.data
    )
    energysites = hass.data[DOMAIN][config_entry.entry_id].energysites.map(
        lambda x: x.coordinator.data
    )

    # Return only the relevant children
    return {
        "vehicles": async_redact_data(vehicles, VEHICLE_REDACT),
        "energysites": async_redact_data(energysites, ENERGY_REDACT),
    }
