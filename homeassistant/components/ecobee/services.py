"""Services for the ecobee integration."""

from enum import StrEnum
from typing import TYPE_CHECKING

import probatio

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.const import CommonServiceArgument
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_platform_entity_service
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN
from .util import ecobee_date, ecobee_time

if TYPE_CHECKING:
    from .climate import Thermostat


class EcobeeService(StrEnum):
    """Store keys for ecobee services."""

    CREATE_VACATION = "create_vacation"
    DELETE_VACATION = "delete_vacation"
    RESUME_PROGRAM = "resume_program"
    SET_FAN_MIN_ON_TIME = "set_fan_min_on_time"
    SET_DST_MODE = "set_dst_mode"
    SET_MIC_MODE = "set_mic_mode"
    SET_OCCUPANCY_MODES = "set_occupancy_modes"
    SET_SENSORS_USED_IN_CLIMATE = "set_sensors_used_in_climate"


class EcobeeServiceArgument(StrEnum):
    """Store keys for ecobee service arguments."""

    VACATION_NAME = "vacation_name"
    COOL_TEMP = "cool_temp"
    HEAT_TEMP = "heat_temp"
    START_DATE = "start_date"
    START_TIME = "start_time"
    END_DATE = "end_date"
    END_TIME = "end_time"
    FAN_MODE = "fan_mode"
    FAN_MIN_ON_TIME = "fan_min_on_time"
    RESUME_ALL = "resume_all"
    DST_ENABLED = "dst_enabled"
    MIC_ENABLED = "mic_enabled"
    AUTO_AWAY = "auto_away"
    FOLLOW_ME = "follow_me"
    PRESET_MODE = "preset_mode"
    DEVICE_IDS = "device_ids"


DEFAULT_RESUME_ALL = False

ECOBEE_THERMOSTATS: HassKey[list[Thermostat]] = HassKey(DOMAIN)

DTGROUP_START_INCLUSIVE_MSG = (
    f"{EcobeeServiceArgument.START_DATE} and {EcobeeServiceArgument.START_TIME}"
    " must be specified together"
)

DTGROUP_END_INCLUSIVE_MSG = (
    f"{EcobeeServiceArgument.END_DATE} and {EcobeeServiceArgument.END_TIME}"
    " must be specified together"
)

CREATE_VACATION_SCHEMA = probatio.Schema(
    {
        probatio.Required(CommonServiceArgument.ENTITY_ID): cv.entity_id,
        probatio.Required(EcobeeServiceArgument.VACATION_NAME): probatio.All(
            cv.string, probatio.Length(max=12)
        ),
        probatio.Required(EcobeeServiceArgument.COOL_TEMP): probatio.Coerce(float),
        probatio.Required(EcobeeServiceArgument.HEAT_TEMP): probatio.Coerce(float),
        probatio.Inclusive(
            EcobeeServiceArgument.START_DATE,
            "dtgroup_start",
            msg=DTGROUP_START_INCLUSIVE_MSG,
        ): ecobee_date,
        probatio.Inclusive(
            EcobeeServiceArgument.START_TIME,
            "dtgroup_start",
            msg=DTGROUP_START_INCLUSIVE_MSG,
        ): ecobee_time,
        probatio.Inclusive(
            EcobeeServiceArgument.END_DATE, "dtgroup_end", msg=DTGROUP_END_INCLUSIVE_MSG
        ): ecobee_date,
        probatio.Inclusive(
            EcobeeServiceArgument.END_TIME, "dtgroup_end", msg=DTGROUP_END_INCLUSIVE_MSG
        ): ecobee_time,
        probatio.Optional(EcobeeServiceArgument.FAN_MODE, default="auto"): probatio.Any(
            "auto", "on"
        ),
        probatio.Optional(
            EcobeeServiceArgument.FAN_MIN_ON_TIME, default=0
        ): probatio.All(int, probatio.Range(min=0, max=60)),
    }
)

DELETE_VACATION_SCHEMA = probatio.Schema(
    {
        probatio.Required(CommonServiceArgument.ENTITY_ID): cv.entity_id,
        probatio.Required(EcobeeServiceArgument.VACATION_NAME): probatio.All(
            cv.string, probatio.Length(max=12)
        ),
    }
)

RESUME_PROGRAM_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CommonServiceArgument.ENTITY_ID): cv.entity_ids,
        probatio.Optional(
            EcobeeServiceArgument.RESUME_ALL, default=DEFAULT_RESUME_ALL
        ): cv.boolean,
    }
)

SET_FAN_MIN_ON_TIME_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CommonServiceArgument.ENTITY_ID): cv.entity_ids,
        probatio.Required(EcobeeServiceArgument.FAN_MIN_ON_TIME): probatio.Coerce(int),
    }
)


@callback
def _async_get_thermostats(hass: HomeAssistant) -> list[Thermostat]:
    """Return loaded ecobee thermostat entities."""
    return hass.data[ECOBEE_THERMOSTATS]


def _create_vacation_service(call: ServiceCall) -> None:
    """Create a vacation on the target thermostat."""
    for thermostat in _async_get_thermostats(call.hass):
        if thermostat.entity_id == call.data[CommonServiceArgument.ENTITY_ID]:
            thermostat.create_vacation(call.data)
            thermostat.schedule_update_ha_state(True)
            break


def _delete_vacation_service(call: ServiceCall) -> None:
    """Delete a vacation on the target thermostat."""
    for thermostat in _async_get_thermostats(call.hass):
        if thermostat.entity_id == call.data[CommonServiceArgument.ENTITY_ID]:
            thermostat.delete_vacation(call.data[EcobeeServiceArgument.VACATION_NAME])
            thermostat.schedule_update_ha_state(True)
            break


def _fan_min_on_time_set_service(call: ServiceCall) -> None:
    """Set the minimum fan on time on the target thermostats."""
    entity_id = call.data.get(CommonServiceArgument.ENTITY_ID)
    thermostats = _async_get_thermostats(call.hass)
    if entity_id:
        thermostats = [
            thermostat
            for thermostat in thermostats
            if thermostat.entity_id in entity_id
        ]

    for thermostat in thermostats:
        thermostat.set_fan_min_on_time(
            str(call.data[EcobeeServiceArgument.FAN_MIN_ON_TIME])
        )
        thermostat.schedule_update_ha_state(True)


def _resume_program_set_service(call: ServiceCall) -> None:
    """Resume the program on the target thermostats."""
    entity_id = call.data.get(CommonServiceArgument.ENTITY_ID)
    thermostats = _async_get_thermostats(call.hass)
    if entity_id:
        thermostats = [
            thermostat
            for thermostat in thermostats
            if thermostat.entity_id in entity_id
        ]

    for thermostat in thermostats:
        thermostat.resume_program(call.data.get(EcobeeServiceArgument.RESUME_ALL))
        thermostat.schedule_update_ha_state(True)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register ecobee services."""
    hass.data[ECOBEE_THERMOSTATS] = []

    hass.services.async_register(
        DOMAIN,
        EcobeeService.CREATE_VACATION,
        _create_vacation_service,
        schema=CREATE_VACATION_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        EcobeeService.DELETE_VACATION,
        _delete_vacation_service,
        schema=DELETE_VACATION_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        EcobeeService.SET_FAN_MIN_ON_TIME,
        _fan_min_on_time_set_service,
        schema=SET_FAN_MIN_ON_TIME_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        EcobeeService.RESUME_PROGRAM,
        _resume_program_set_service,
        schema=RESUME_PROGRAM_SCHEMA,
    )
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        EcobeeService.SET_DST_MODE,
        entity_domain=CLIMATE_DOMAIN,
        func="set_dst_mode",
        schema={probatio.Required(EcobeeServiceArgument.DST_ENABLED): cv.boolean},
    )
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        EcobeeService.SET_MIC_MODE,
        entity_domain=CLIMATE_DOMAIN,
        func="set_mic_mode",
        schema={probatio.Required(EcobeeServiceArgument.MIC_ENABLED): cv.boolean},
    )
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        EcobeeService.SET_OCCUPANCY_MODES,
        entity_domain=CLIMATE_DOMAIN,
        func="set_occupancy_modes",
        schema={
            probatio.Optional(EcobeeServiceArgument.AUTO_AWAY): cv.boolean,
            probatio.Optional(EcobeeServiceArgument.FOLLOW_ME): cv.boolean,
        },
    )
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        EcobeeService.SET_SENSORS_USED_IN_CLIMATE,
        entity_domain=CLIMATE_DOMAIN,
        func="set_sensors_used_in_climate",
        schema={
            probatio.Optional(EcobeeServiceArgument.PRESET_MODE): cv.string,
            probatio.Required(EcobeeServiceArgument.DEVICE_IDS): probatio.EnsureList(),
        },
    )
