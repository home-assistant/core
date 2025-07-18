"""Support for Renault services."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import DOMAIN
from .renault_vehicle import RenaultVehicleProxy

if TYPE_CHECKING:
    from . import RenaultConfigEntry

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
        vol.Optional("monday"): vol.Any(None, SERVICE_CHARGE_SET_SCHEDULE_DAY_SCHEMA),
        vol.Optional("tuesday"): vol.Any(None, SERVICE_CHARGE_SET_SCHEDULE_DAY_SCHEMA),
        vol.Optional("wednesday"): vol.Any(
            None, SERVICE_CHARGE_SET_SCHEDULE_DAY_SCHEMA
        ),
        vol.Optional("thursday"): vol.Any(None, SERVICE_CHARGE_SET_SCHEDULE_DAY_SCHEMA),
        vol.Optional("friday"): vol.Any(None, SERVICE_CHARGE_SET_SCHEDULE_DAY_SCHEMA),
        vol.Optional("saturday"): vol.Any(None, SERVICE_CHARGE_SET_SCHEDULE_DAY_SCHEMA),
        vol.Optional("sunday"): vol.Any(None, SERVICE_CHARGE_SET_SCHEDULE_DAY_SCHEMA),
    }
)
SERVICE_CHARGE_SET_SCHEDULES_SCHEMA = SERVICE_VEHICLE_SCHEMA.extend(
    {
        vol.Required(ATTR_SCHEDULES): vol.All(
            cv.ensure_list, [SERVICE_CHARGE_SET_SCHEDULE_SCHEMA]
        ),
    }
)

SERVICE_AC_SET_SCHEDULE_DAY_SCHEMA = vol.Schema(
    {
        vol.Required("readyAtTime"): cv.string,
    }
)

SERVICE_AC_SET_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Required("id"): cv.positive_int,
        vol.Optional("activated"): cv.boolean,
        vol.Optional("monday"): vol.Any(None, SERVICE_AC_SET_SCHEDULE_DAY_SCHEMA),
        vol.Optional("tuesday"): vol.Any(None, SERVICE_AC_SET_SCHEDULE_DAY_SCHEMA),
        vol.Optional("wednesday"): vol.Any(None, SERVICE_AC_SET_SCHEDULE_DAY_SCHEMA),
        vol.Optional("thursday"): vol.Any(None, SERVICE_AC_SET_SCHEDULE_DAY_SCHEMA),
        vol.Optional("friday"): vol.Any(None, SERVICE_AC_SET_SCHEDULE_DAY_SCHEMA),
        vol.Optional("saturday"): vol.Any(None, SERVICE_AC_SET_SCHEDULE_DAY_SCHEMA),
        vol.Optional("sunday"): vol.Any(None, SERVICE_AC_SET_SCHEDULE_DAY_SCHEMA),
    }
)
SERVICE_AC_SET_SCHEDULES_SCHEMA = SERVICE_VEHICLE_SCHEMA.extend(
    {
        vol.Required(ATTR_SCHEDULES): vol.All(
            cv.ensure_list, [SERVICE_AC_SET_SCHEDULE_SCHEMA]
        ),
    }
)

SERVICE_AC_CANCEL = "ac_cancel"
SERVICE_AC_START = "ac_start"
SERVICE_CHARGE_SET_SCHEDULES = "charge_set_schedules"
SERVICE_AC_SET_SCHEDULES = "ac_set_schedules"
SERVICES = [
    SERVICE_AC_CANCEL,
    SERVICE_AC_START,
    SERVICE_CHARGE_SET_SCHEDULES,
    SERVICE_AC_SET_SCHEDULES,
]


async def ac_cancel(service_call: ServiceCall) -> None:
    """Cancel A/C."""
    proxy = get_vehicle_proxy(service_call)

    LOGGER.debug("A/C cancel attempt")
    result = await proxy.set_ac_stop()
    LOGGER.debug("A/C cancel result: %s", result)


async def ac_start(service_call: ServiceCall) -> None:
    """Start A/C."""
    temperature: float = service_call.data[ATTR_TEMPERATURE]
    when: datetime | None = service_call.data.get(ATTR_WHEN)
    proxy = get_vehicle_proxy(service_call)

    LOGGER.debug("A/C start attempt: %s / %s", temperature, when)
    result = await proxy.set_ac_start(temperature, when)
    LOGGER.debug("A/C start result: %s", result.raw_data)


async def charge_set_schedules(service_call: ServiceCall) -> None:
    """Set charge schedules."""
    schedules: list[dict[str, Any]] = service_call.data[ATTR_SCHEDULES]
    proxy = get_vehicle_proxy(service_call)
    charge_schedules = await proxy.get_charging_settings()
    for schedule in schedules:
        charge_schedules.update(schedule)

    if TYPE_CHECKING:
        assert charge_schedules.schedules is not None
    LOGGER.debug("Charge set schedules attempt: %s", schedules)
    result = await proxy.set_charge_schedules(charge_schedules.schedules)

    LOGGER.debug("Charge set schedules result: %s", result)
    LOGGER.debug(
        "It may take some time before these changes are reflected in your vehicle"
    )


async def ac_set_schedules(service_call: ServiceCall) -> None:
    """Set A/C schedules."""
    schedules: list[dict[str, Any]] = service_call.data[ATTR_SCHEDULES]
    proxy = get_vehicle_proxy(service_call)
    hvac_schedules = await proxy.get_hvac_settings()

    for schedule in schedules:
        hvac_schedules.update(schedule)

    if TYPE_CHECKING:
        assert hvac_schedules.schedules is not None
    LOGGER.debug("HVAC set schedules attempt: %s", schedules)
    result = await proxy.set_hvac_schedules(hvac_schedules.schedules)

    LOGGER.debug("HVAC set schedules result: %s", result)
    LOGGER.debug(
        "It may take some time before these changes are reflected in your vehicle"
    )


def get_vehicle_proxy(service_call: ServiceCall) -> RenaultVehicleProxy:
    """Get vehicle from service_call data."""
    device_registry = dr.async_get(service_call.hass)
    device_id = service_call.data[ATTR_VEHICLE]
    device_entry = device_registry.async_get(device_id)
    if device_entry is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_device_id",
            translation_placeholders={"device_id": device_id},
        )

    loaded_entries: list[RenaultConfigEntry] = [
        entry
        for entry in service_call.hass.config_entries.async_loaded_entries(DOMAIN)
        if entry.entry_id in device_entry.config_entries
    ]
    for entry in loaded_entries:
        for vin, vehicle in entry.runtime_data.vehicles.items():
            if (DOMAIN, vin) in device_entry.identifiers:
                return vehicle
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="no_config_entry_for_device",
        translation_placeholders={"device_id": device_entry.name or device_id},
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Renault services."""

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
        SERVICE_AC_SET_SCHEDULES,
        ac_set_schedules,
        schema=SERVICE_AC_SET_SCHEDULES_SCHEMA,
    )
