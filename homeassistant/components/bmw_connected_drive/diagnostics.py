"""Diagnostics support for the BMW Connected Drive integration."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from bimmer_connected.utils import MyBMWJSONEncoder

from homeassistant.components.diagnostics.util import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntry

from .const import CONF_REFRESH_TOKEN, DOMAIN

if TYPE_CHECKING:
    from bimmer_connected.vehicle import MyBMWVehicle

    from .coordinator import BMWDataUpdateCoordinator

TO_REDACT_INFO = [CONF_USERNAME, CONF_PASSWORD, CONF_REFRESH_TOKEN]
TO_REDACT_DATA = [
    "lat",
    "latitude",
    "lon",
    "longitude",
    "heading",
    "vin",
    "licensePlate",
    "name",
    "city",
    "street",
    "streetNumber",
    "postalCode",
    "phone",
    "formatted",
    "subtitle",
]


def vehicle_to_dict(vehicle: MyBMWVehicle) -> dict:
    """Convert a MyBMWVehicle to a dictionary using MyBMWJSONEncoder."""
    retval: dict = json.loads(json.dumps(vehicle, cls=MyBMWJSONEncoder))
    return retval


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: BMWDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    diagnostics_data = {
        "info": async_redact_data(config_entry.data, TO_REDACT_INFO),
        "data": [
            async_redact_data(vehicle_to_dict(vehicle), TO_REDACT_DATA)
            for vehicle in coordinator.account.vehicles
        ],
        "fingerprint": async_redact_data(
            await coordinator.account.get_fingerprints(), TO_REDACT_DATA
        ),
    }

    return diagnostics_data


async def async_get_device_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    coordinator: BMWDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    vin = next(iter(device.identifiers))[1]
    vehicle = coordinator.account.get_vehicle(vin)

    if not vehicle:
        raise HomeAssistantError("Vehicle not found")

    diagnostics_data = {
        "info": async_redact_data(config_entry.data, TO_REDACT_INFO),
        "data": async_redact_data(vehicle_to_dict(vehicle), TO_REDACT_DATA),
        # Always have to get the full fingerprint as the VIN is redacted beforehand by the library
        "fingerprint": async_redact_data(
            await coordinator.account.get_fingerprints(), TO_REDACT_DATA
        ),
    }

    return diagnostics_data
