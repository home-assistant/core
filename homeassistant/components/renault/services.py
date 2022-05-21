"""Support for Renault services."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import DOMAIN
from .renault_hub import RenaultHub
from .renault_vehicle import RenaultVehicleProxy

LOGGER = logging.getLogger(__name__)

ATTR_SCHEDULES = "schedules"
ATTR_TEMPERATURE = "temperature"
ATTR_VEHICLE = "vehicle"
ATTR_WHEN = "when"

SERVICE_VEHICLE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_VEHICLE): cv.string,
    }
)
SERVICE_AC_START_SCHEMA = SERVICE_VEHICLE_SCHEMA.extend(
    {
        vol.Required(ATTR_TEMPERATURE): cv.positive_float,
        vol.Optional(ATTR_WHEN): cv.datetime,
    }
)
SERVICE_CHARGE_SET_SCHEDULE_DAY_SCHEMA = vol.Schema(
    {
        vol.Required("startTime"): cv.string,
        vol.Required("duration"): cv.positive_int,
    }
)
SERVICE_CHARGE_SET_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Required("id"): cv.positive_int,
        vol.Optional("activated"): cv.boolean,
        vol.Optional("monday"): vol.Schema(SERVICE_CHARGE_SET_SCHEDULE_DAY_SCHEMA),
        vol.Optional("tuesday"): vol.Schema(SERVICE_CHARGE_SET_SCHEDULE_DAY_SCHEMA),
        vol.Optional("wednesday"): vol.Schema(SERVICE_CHARGE_SET_SCHEDULE_DAY_SCHEMA),
        vol.Optional("thursday"): vol.Schema(SERVICE_CHARGE_SET_SCHEDULE_DAY_SCHEMA),
        vol.Optional("friday"): vol.Schema(SERVICE_CHARGE_SET_SCHEDULE_DAY_SCHEMA),
        vol.Optional("saturday"): vol.Schema(SERVICE_CHARGE_SET_SCHEDULE_DAY_SCHEMA),
        vol.Optional("sunday"): vol.Schema(SERVICE_CHARGE_SET_SCHEDULE_DAY_SCHEMA),
    }
)
SERVICE_CHARGE_SET_SCHEDULES_SCHEMA = SERVICE_VEHICLE_SCHEMA.extend(
    {
        vol.Required(ATTR_SCHEDULES): vol.All(
            cv.ensure_list, [SERVICE_CHARGE_SET_SCHEDULE_SCHEMA]
        ),
    }
)

SERVICE_AC_CANCEL = "ac_cancel"
SERVICE_AC_START = "ac_start"
SERVICE_CHARGE_SET_SCHEDULES = "charge_set_schedules"
SERVICE_CHARGE_START = "charge_start"
SERVICES = [
    SERVICE_AC_CANCEL,
    SERVICE_AC_START,
    SERVICE_CHARGE_SET_SCHEDULES,
    SERVICE_CHARGE_START,
]


def setup_services(hass: HomeAssistant) -> None:
    """Register the Renault services."""

    async def ac_cancel(service_call: ServiceCall) -> None:
        """Cancel A/C."""
        proxy = get_vehicle_proxy(service_call.data)

        LOGGER.debug("A/C cancel attempt")
        result = await proxy.vehicle.set_ac_stop()
        LOGGER.debug("A/C cancel result: %s", result)

    async def ac_start(service_call: ServiceCall) -> None:
        """Start A/C."""
        temperature: float = service_call.data[ATTR_TEMPERATURE]
        when: datetime | None = service_call.data.get(ATTR_WHEN)
        proxy = get_vehicle_proxy(service_call.data)

        LOGGER.debug("A/C start attempt: %s / %s", temperature, when)
        result = await proxy.vehicle.set_ac_start(temperature, when)
        LOGGER.debug("A/C start result: %s", result.raw_data)

    async def charge_set_schedules(service_call: ServiceCall) -> None:
        """Set charge schedules."""
        schedules: list[dict[str, Any]] = service_call.data[ATTR_SCHEDULES]
        proxy = get_vehicle_proxy(service_call.data)
        charge_schedules = await proxy.vehicle.get_charging_settings()
        for schedule in schedules:
            charge_schedules.update(schedule)

        if TYPE_CHECKING:
            assert charge_schedules.schedules is not None
        LOGGER.debug("Charge set schedules attempt: %s", schedules)
        result = await proxy.vehicle.set_charge_schedules(charge_schedules.schedules)
        LOGGER.debug("Charge set schedules result: %s", result)
        LOGGER.debug(
            "It may take some time before these changes are reflected in your vehicle"
        )

    async def charge_start(service_call: ServiceCall) -> None:
        """Start charge."""
        # The Renault start charge service has been replaced by a
        # dedicated button entity and marked as deprecated
        LOGGER.warning(
            "The 'renault.charge_start' service is deprecated and "
            "replaced by a dedicated start charge button entity; please "
            "use that entity to start the charge instead"
        )

        proxy = get_vehicle_proxy(service_call.data)

        LOGGER.debug("Charge start attempt")
        result = await proxy.vehicle.set_charge_start()
        LOGGER.debug("Charge start result: %s", result)

    def get_vehicle_proxy(service_call_data: Mapping) -> RenaultVehicleProxy:
        """Get vehicle from service_call data."""
        device_registry = dr.async_get(hass)
        device_id = service_call_data[ATTR_VEHICLE]
        device_entry = device_registry.async_get(device_id)
        if device_entry is None:
            raise ValueError(f"Unable to find device with id: {device_id}")

        proxy: RenaultHub
        for proxy in hass.data[DOMAIN].values():
            for vin, vehicle in proxy.vehicles.items():
                if (DOMAIN, vin) in device_entry.identifiers:
                    return vehicle
        raise ValueError(f"Unable to find vehicle with VIN: {device_entry.identifiers}")

    hass.services.async_register(
        DOMAIN,
        SERVICE_AC_CANCEL,
        ac_cancel,
        schema=SERVICE_VEHICLE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_AC_START,
        ac_start,
        schema=SERVICE_AC_START_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CHARGE_SET_SCHEDULES,
        charge_set_schedules,
        schema=SERVICE_CHARGE_SET_SCHEDULES_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CHARGE_START,
        charge_start,
        schema=SERVICE_VEHICLE_SCHEMA,
    )


def unload_services(hass: HomeAssistant) -> None:
    """Unload Renault services."""
    for service in SERVICES:
        hass.services.async_remove(DOMAIN, service)
