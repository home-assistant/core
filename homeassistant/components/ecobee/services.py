"""Services for the ecobee integration."""

from typing import TYPE_CHECKING

import probatio

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_platform_entity_service

from .const import DOMAIN
from .util import ecobee_date, ecobee_time

if TYPE_CHECKING:
    from .climate import Thermostat

ATTR_AUTO_AWAY = "auto_away"
ATTR_COOL_TEMP = "cool_temp"
ATTR_DST_ENABLED = "dst_enabled"
ATTR_END_DATE = "end_date"
ATTR_END_TIME = "end_time"
ATTR_FAN_MIN_ON_TIME = "fan_min_on_time"
ATTR_FAN_MODE = "fan_mode"
ATTR_FOLLOW_ME = "follow_me"
ATTR_HEAT_TEMP = "heat_temp"
ATTR_MIC_ENABLED = "mic_enabled"
ATTR_PRESET_MODE = "preset_mode"
ATTR_RESUME_ALL = "resume_all"
ATTR_SENSOR_LIST = "device_ids"
ATTR_START_DATE = "start_date"
ATTR_START_TIME = "start_time"
ATTR_VACATION_NAME = "vacation_name"

DEFAULT_RESUME_ALL = False

DATA_THERMOSTATS = "thermostats"

SERVICE_CREATE_VACATION = "create_vacation"
SERVICE_DELETE_VACATION = "delete_vacation"
SERVICE_RESUME_PROGRAM = "resume_program"
SERVICE_SET_DST_MODE = "set_dst_mode"
SERVICE_SET_FAN_MIN_ON_TIME = "set_fan_min_on_time"
SERVICE_SET_MIC_MODE = "set_mic_mode"
SERVICE_SET_OCCUPANCY_MODES = "set_occupancy_modes"
SERVICE_SET_SENSORS_USED_IN_CLIMATE = "set_sensors_used_in_climate"

DTGROUP_START_INCLUSIVE_MSG = (
    f"{ATTR_START_DATE} and {ATTR_START_TIME} must be specified together"
)

DTGROUP_END_INCLUSIVE_MSG = (
    f"{ATTR_END_DATE} and {ATTR_END_TIME} must be specified together"
)

CREATE_VACATION_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_ENTITY_ID): cv.entity_id,
        probatio.Required(ATTR_VACATION_NAME): probatio.All(
            cv.string, probatio.Length(max=12)
        ),
        probatio.Required(ATTR_COOL_TEMP): probatio.Coerce(float),
        probatio.Required(ATTR_HEAT_TEMP): probatio.Coerce(float),
        probatio.Inclusive(
            ATTR_START_DATE, "dtgroup_start", msg=DTGROUP_START_INCLUSIVE_MSG
        ): ecobee_date,
        probatio.Inclusive(
            ATTR_START_TIME, "dtgroup_start", msg=DTGROUP_START_INCLUSIVE_MSG
        ): ecobee_time,
        probatio.Inclusive(
            ATTR_END_DATE, "dtgroup_end", msg=DTGROUP_END_INCLUSIVE_MSG
        ): ecobee_date,
        probatio.Inclusive(
            ATTR_END_TIME, "dtgroup_end", msg=DTGROUP_END_INCLUSIVE_MSG
        ): ecobee_time,
        probatio.Optional(ATTR_FAN_MODE, default="auto"): probatio.Any("auto", "on"),
        probatio.Optional(ATTR_FAN_MIN_ON_TIME, default=0): probatio.All(
            int, probatio.Range(min=0, max=60)
        ),
    }
)

DELETE_VACATION_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_ENTITY_ID): cv.entity_id,
        probatio.Required(ATTR_VACATION_NAME): probatio.All(
            cv.string, probatio.Length(max=12)
        ),
    }
)

RESUME_PROGRAM_SCHEMA = probatio.Schema(
    {
        probatio.Optional(ATTR_ENTITY_ID): cv.entity_ids,
        probatio.Optional(ATTR_RESUME_ALL, default=DEFAULT_RESUME_ALL): cv.boolean,
    }
)

SET_FAN_MIN_ON_TIME_SCHEMA = probatio.Schema(
    {
        probatio.Optional(ATTR_ENTITY_ID): cv.entity_ids,
        probatio.Required(ATTR_FAN_MIN_ON_TIME): probatio.Coerce(int),
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
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_DST_MODE,
        entity_domain=CLIMATE_DOMAIN,
        func="set_dst_mode",
        schema={probatio.Required(ATTR_DST_ENABLED): cv.boolean},
    )
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_MIC_MODE,
        entity_domain=CLIMATE_DOMAIN,
        func="set_mic_mode",
        schema={probatio.Required(ATTR_MIC_ENABLED): cv.boolean},
    )
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_OCCUPANCY_MODES,
        entity_domain=CLIMATE_DOMAIN,
        func="set_occupancy_modes",
        schema={
            probatio.Optional(ATTR_AUTO_AWAY): cv.boolean,
            probatio.Optional(ATTR_FOLLOW_ME): cv.boolean,
        },
    )
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_SENSORS_USED_IN_CLIMATE,
        entity_domain=CLIMATE_DOMAIN,
        func="set_sensors_used_in_climate",
        schema={
            probatio.Optional(ATTR_PRESET_MODE): cv.string,
            probatio.Required(ATTR_SENSOR_LIST): probatio.EnsureList(),
        },
    )
