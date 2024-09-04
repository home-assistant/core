"""Diagnostics support for the BMW Connected Drive integration."""

from __future__ import annotations

from dataclasses import asdict
import json
from typing import TYPE_CHECKING, Any

from bimmer_connected.utils import MyBMWJSONEncoder

from homeassistant.components.diagnostics.util import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from . import BMWConfigEntry
from .const import CONF_REFRESH_TOKEN

if TYPE_CHECKING:
    from bimmer_connected.vehicle import MyBMWVehicle


TO_REDACT_INFO = [CONF_USERNAME, CONF_PASSWORD, CONF_REFRESH_TOKEN]
TO_REDACT_DATA = [
    "lat",
    "latitude",
    "lon",
    "longitude",
    "heading",
    "vin",
    "licensePlate",
    "city",
    "street",
    "streetNumber",
    "postalCode",
    "phone",
    "formatted",
    "subtitle",
]


def vehicle_to_dict(vehicle: MyBMWVehicle | None) -> dict:
    """Convert a MyBMWVehicle to a dictionary using MyBMWJSONEncoder."""
    retval: dict = json.loads(json.dumps(vehicle, cls=MyBMWJSONEncoder))
    return retval


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: BMWConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = config_entry.runtime_data.coordinator

    coordinator.account.config.log_responses = True
    await coordinator.account.get_vehicles(force_init=True)

    diagnostics_data = {
        "info": async_redact_data(config_entry.data, TO_REDACT_INFO),
        "data": [
            async_redact_data(vehicle_to_dict(vehicle), TO_REDACT_DATA)
            for vehicle in coordinator.account.vehicles
        ],
        "fingerprint": async_redact_data(
            [asdict(r) for r in coordinator.account.get_stored_responses()],
            TO_REDACT_DATA,
        ),
    }

    coordinator.account.config.log_responses = False

    return diagnostics_data


async def async_get_device_diagnostics(
    hass: HomeAssistant, config_entry: BMWConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    coordinator = config_entry.runtime_data.coordinator

    coordinator.account.config.log_responses = True
    await coordinator.account.get_vehicles(force_init=True)

    vin = next(iter(device.identifiers))[1]
    vehicle = coordinator.account.get_vehicle(vin)

    diagnostics_data = {
        "info": async_redact_data(config_entry.data, TO_REDACT_INFO),
        "data": async_redact_data(vehicle_to_dict(vehicle), TO_REDACT_DATA),
        # Always have to get the full fingerprint as the VIN is redacted beforehand by the library
        "fingerprint": async_redact_data(
            [asdict(r) for r in coordinator.account.get_stored_responses()],
            TO_REDACT_DATA,
        ),
    }

    coordinator.account.config.log_responses = False

    return diagnostics_data
