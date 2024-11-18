"""Diagnostics support for Renault."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from . import RenaultConfigEntry
from .const import CONF_KAMEREON_ACCOUNT_ID
from .renault_vehicle import RenaultVehicleProxy

TO_REDACT = {
    CONF_KAMEREON_ACCOUNT_ID,
    CONF_PASSWORD,
    CONF_USERNAME,
    "radioCode",
    "registrationNumber",
    "vin",
    "gpsLatitude",
    "gpsLongitude",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: RenaultConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(entry.data, TO_REDACT),
        },
        "vehicles": [
            _get_vehicle_diagnostics(vehicle)
            for vehicle in entry.runtime_data.vehicles.values()
        ],
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: RenaultConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    vin = next(iter(device.identifiers))[1]
    vehicle = entry.runtime_data.vehicles[vin]

    return _get_vehicle_diagnostics(vehicle)


def _get_vehicle_diagnostics(vehicle: RenaultVehicleProxy) -> dict[str, Any]:
    """Return diagnostics for a device."""
    return {
        "details": async_redact_data(vehicle.details.raw_data, TO_REDACT),
        "data": {
            key: async_redact_data(
                coordinator.data.raw_data if coordinator.data else None, TO_REDACT
            )
            for key, coordinator in vehicle.coordinators.items()
        },
    }
