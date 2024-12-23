"""Schema definitions for LCN configuration and websockets api."""

import voluptuous as vol

from homeassistant.components.climate import DEFAULT_MAX_TEMP, DEFAULT_MIN_TEMP
from homeassistant.const import (
    CONF_SCENE,
    CONF_SOURCE,
    CONF_UNIT_OF_MEASUREMENT,
    UnitOfTemperature,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import VolDictType

from .const import (
    BINSENSOR_PORTS,
    CONF_DIMMABLE,
    CONF_LOCKABLE,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_MOTOR,
    CONF_OUTPUT,
    CONF_OUTPUTS,
    CONF_REGISTER,
    CONF_REVERSE_TIME,
    CONF_SETPOINT,
    CONF_TRANSITION,
    KEYS,
    LED_PORTS,
    LOGICOP_PORTS,
    MOTOR_PORTS,
    MOTOR_REVERSE_TIME,
    OUTPUT_PORTS,
    RELAY_PORTS,
    S0_INPUTS,
    SETPOINTS,
    THRESHOLDS,
    VAR_UNITS,
    VARIABLES,
)

ADDRESS_SCHEMA = vol.Coerce(tuple)

#
# Domain data
#

DOMAIN_DATA_BINARY_SENSOR: VolDictType = {
    vol.Required(CONF_SOURCE): vol.All(
        vol.Upper, vol.In(SETPOINTS + KEYS + BINSENSOR_PORTS)
    ),
}


DOMAIN_DATA_CLIMATE: VolDictType = {
    vol.Required(CONF_SOURCE): vol.All(vol.Upper, vol.In(VARIABLES)),
    vol.Required(CONF_SETPOINT): vol.All(vol.Upper, vol.In(VARIABLES + SETPOINTS)),
    vol.Optional(CONF_MAX_TEMP, default=DEFAULT_MAX_TEMP): vol.Coerce(float),
    vol.Optional(CONF_MIN_TEMP, default=DEFAULT_MIN_TEMP): vol.Coerce(float),
    vol.Optional(CONF_LOCKABLE, default=False): vol.Coerce(bool),
    vol.Optional(CONF_UNIT_OF_MEASUREMENT, default=UnitOfTemperature.CELSIUS): vol.In(
        UnitOfTemperature.CELSIUS, UnitOfTemperature.FAHRENHEIT
    ),
}


DOMAIN_DATA_COVER: VolDictType = {
    vol.Required(CONF_MOTOR): vol.All(vol.Upper, vol.In(MOTOR_PORTS)),
    vol.Optional(CONF_REVERSE_TIME, default="rt1200"): vol.All(
        vol.Upper, vol.In(MOTOR_REVERSE_TIME)
    ),
}


DOMAIN_DATA_LIGHT: VolDictType = {
    vol.Required(CONF_OUTPUT): vol.All(vol.Upper, vol.In(OUTPUT_PORTS + RELAY_PORTS)),
    vol.Optional(CONF_DIMMABLE, default=False): vol.Coerce(bool),
    vol.Optional(CONF_TRANSITION, default=0): vol.All(
        vol.Coerce(float), vol.Range(min=0.0, max=486.0)
    ),
}


DOMAIN_DATA_SCENE: VolDictType = {
    vol.Required(CONF_REGISTER): vol.All(vol.Coerce(int), vol.Range(0, 9)),
    vol.Required(CONF_SCENE): vol.All(vol.Coerce(int), vol.Range(0, 9)),
    vol.Optional(CONF_OUTPUTS, default=[]): vol.All(
        cv.ensure_list, [vol.All(vol.Upper, vol.In(OUTPUT_PORTS + RELAY_PORTS))]
    ),
    vol.Optional(CONF_TRANSITION, default=0): vol.Any(
        vol.All(vol.Coerce(int), vol.Range(min=0.0, max=486.0))
    ),
}

DOMAIN_DATA_SENSOR: VolDictType = {
    vol.Required(CONF_SOURCE): vol.All(
        vol.Upper,
        vol.In(
            VARIABLES + SETPOINTS + THRESHOLDS + S0_INPUTS + LED_PORTS + LOGICOP_PORTS
        ),
    ),
    vol.Optional(CONF_UNIT_OF_MEASUREMENT, default="native"): vol.All(
        vol.Upper, vol.In(VAR_UNITS)
    ),
}


DOMAIN_DATA_SWITCH: VolDictType = {
    vol.Required(CONF_OUTPUT): vol.All(
        vol.Upper,
        vol.In(OUTPUT_PORTS + RELAY_PORTS + SETPOINTS + KEYS),
    ),
}
