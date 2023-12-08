"""Diagnostics support for Renault."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from . import RenaultHub
from .const import CONF_KAMEREON_ACCOUNT_ID, DOMAIN
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
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    renault_hub: RenaultHub = hass.data[DOMAIN][entry.entry_id]

    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(entry.data, TO_REDACT),
        },
        "vehicles": [
            _get_vehicle_diagnostics(vehicle)
            for vehicle in renault_hub.vehicles.values()
        ],
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    renault_hub: RenaultHub = hass.data[DOMAIN][entry.entry_id]
    vin = next(iter(device.identifiers))[1]
    vehicle = renault_hub.vehicles[vin]

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
