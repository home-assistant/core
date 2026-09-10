"""Services for the ecobee integration."""

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .util import ecobee_date, ecobee_time

if TYPE_CHECKING:
    from .climate import Thermostat

ATTR_COOL_TEMP = "cool_temp"
ATTR_END_DATE = "end_date"
ATTR_END_TIME = "end_time"
ATTR_FAN_MIN_ON_TIME = "fan_min_on_time"
ATTR_FAN_MODE = "fan_mode"
ATTR_HEAT_TEMP = "heat_temp"
ATTR_RESUME_ALL = "resume_all"
ATTR_START_DATE = "start_date"
ATTR_START_TIME = "start_time"
ATTR_VACATION_NAME = "vacation_name"

DEFAULT_RESUME_ALL = False

DATA_THERMOSTATS = "thermostats"

SERVICE_CREATE_VACATION = "create_vacation"
SERVICE_DELETE_VACATION = "delete_vacation"
SERVICE_RESUME_PROGRAM = "resume_program"
SERVICE_SET_FAN_MIN_ON_TIME = "set_fan_min_on_time"

DTGROUP_START_INCLUSIVE_MSG = (
    f"{ATTR_START_DATE} and {ATTR_START_TIME} must be specified together"
)

DTGROUP_END_INCLUSIVE_MSG = (
    f"{ATTR_END_DATE} and {ATTR_END_TIME} must be specified together"
)

CREATE_VACATION_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_VACATION_NAME): vol.All(cv.string, vol.Length(max=12)),
        vol.Required(ATTR_COOL_TEMP): vol.Coerce(float),
        vol.Required(ATTR_HEAT_TEMP): vol.Coerce(float),
        vol.Inclusive(
            ATTR_START_DATE, "dtgroup_start", msg=DTGROUP_START_INCLUSIVE_MSG
        ): ecobee_date,
        vol.Inclusive(
            ATTR_START_TIME, "dtgroup_start", msg=DTGROUP_START_INCLUSIVE_MSG
        ): ecobee_time,
        vol.Inclusive(
            ATTR_END_DATE, "dtgroup_end", msg=DTGROUP_END_INCLUSIVE_MSG
        ): ecobee_date,
        vol.Inclusive(
            ATTR_END_TIME, "dtgroup_end", msg=DTGROUP_END_INCLUSIVE_MSG
        ): ecobee_time,
        vol.Optional(ATTR_FAN_MODE, default="auto"): vol.Any("auto", "on"),
        vol.Optional(ATTR_FAN_MIN_ON_TIME, default=0): vol.All(
            int, vol.Range(min=0, max=60)
        ),
    }
)

DELETE_VACATION_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_VACATION_NAME): vol.All(cv.string, vol.Length(max=12)),
    }
)

RESUME_PROGRAM_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Optional(ATTR_RESUME_ALL, default=DEFAULT_RESUME_ALL): cv.boolean,
    }
)

SET_FAN_MIN_ON_TIME_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(ATTR_FAN_MIN_ON_TIME): vol.Coerce(int),
    }
)


@callback
def _async_get_thermostats(hass: HomeAssistant) -> list[Thermostat]:
    """Return loaded ecobee thermostat entities."""
    # pylint: disable-next=home-assistant-use-runtime-data
    return hass.data[DOMAIN][DATA_THERMOSTATS]


def _create_vacation_service(call: ServiceCall) -> None:
    """Create a vacation on the target thermostat."""
    for thermostat in _async_get_thermostats(call.hass):
        if thermostat.entity_id == call.data[ATTR_ENTITY_ID]:
            thermostat.create_vacation(call.data)
            thermostat.schedule_update_ha_state(True)
            break


def _delete_vacation_service(call: ServiceCall) -> None:
    """Delete a vacation on the target thermostat."""
    for thermostat in _async_get_thermostats(call.hass):
        if thermostat.entity_id == call.data[ATTR_ENTITY_ID]:
            thermostat.delete_vacation(call.data[ATTR_VACATION_NAME])
            thermostat.schedule_update_ha_state(True)
            break


def _fan_min_on_time_set_service(call: ServiceCall) -> None:
    """Set the minimum fan on time on the target thermostats."""
    entity_id = call.data.get(ATTR_ENTITY_ID)
    thermostats = _async_get_thermostats(call.hass)
    if entity_id:
        thermostats = [
            thermostat
            for thermostat in thermostats
            if thermostat.entity_id in entity_id
        ]

    for thermostat in thermostats:
        thermostat.set_fan_min_on_time(str(call.data[ATTR_FAN_MIN_ON_TIME]))
        thermostat.schedule_update_ha_state(True)


def _resume_program_set_service(call: ServiceCall) -> None:
    """Resume the program on the target thermostats."""
    entity_id = call.data.get(ATTR_ENTITY_ID)
    thermostats = _async_get_thermostats(call.hass)
    if entity_id:
        thermostats = [
            thermostat
            for thermostat in thermostats
            if thermostat.entity_id in entity_id
        ]

    for thermostat in thermostats:
        thermostat.resume_program(call.data.get(ATTR_RESUME_ALL))
        thermostat.schedule_update_ha_state(True)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register ecobee services."""
    # pylint: disable-next=home-assistant-use-runtime-data
    hass.data.setdefault(DOMAIN, {})[DATA_THERMOSTATS] = []

    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_VACATION,
        _create_vacation_service,
        schema=CREATE_VACATION_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_VACATION,
        _delete_vacation_service,
        schema=DELETE_VACATION_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_FAN_MIN_ON_TIME,
        _fan_min_on_time_set_service,
        schema=SET_FAN_MIN_ON_TIME_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESUME_PROGRAM,
        _resume_program_set_service,
        schema=RESUME_PROGRAM_SCHEMA,
    )
