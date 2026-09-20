"""Schema definitions for LCN configuration and websockets api."""

import probatio

from homeassistant.components.climate import DEFAULT_MAX_TEMP, DEFAULT_MIN_TEMP
from homeassistant.const import (
    CONF_SCENE,
    CONF_SOURCE,
    CONF_UNIT_OF_MEASUREMENT,
    UnitOfTemperature,
)
from homeassistant.helpers import config_validation as cv
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
    CONF_POSITIONING_MODE,
    CONF_REGISTER,
    CONF_REVERSE_TIME,
    CONF_SETPOINT,
    CONF_TARGET_VALUE_LOCKED,
    CONF_TRANSITION,
    KEYS,
    LED_PORTS,
    LOGICOP_PORTS,
    MOTOR_PORTS,
    MOTOR_POSITIONING_MODES,
    MOTOR_REVERSE_TIMES,
    OUTPUT_PORTS,
    RELAY_PORTS,
    S0_INPUTS,
    SETPOINTS,
    THRESHOLDS,
    VAR_UNITS,
    VARIABLES,
)

ADDRESS_SCHEMA = probatio.Coerce(tuple)

#
# Domain data
#

DOMAIN_DATA_BINARY_SENSOR: VolDictType = {
    probatio.Required(CONF_SOURCE): probatio.All(
        probatio.Upper, probatio.In(SETPOINTS + KEYS + BINSENSOR_PORTS)
    ),
}


DOMAIN_DATA_CLIMATE: VolDictType = {
    probatio.Required(CONF_SOURCE): probatio.All(
        probatio.Upper, probatio.In(VARIABLES)
    ),
    probatio.Required(CONF_SETPOINT): probatio.All(
        probatio.Upper, probatio.In(VARIABLES + SETPOINTS)
    ),
    probatio.Optional(CONF_MAX_TEMP, default=DEFAULT_MAX_TEMP): probatio.Coerce(float),
    probatio.Optional(CONF_MIN_TEMP, default=DEFAULT_MIN_TEMP): probatio.Coerce(float),
    probatio.Optional(CONF_LOCKABLE, default=False): probatio.Coerce(bool),
    probatio.Optional(CONF_TARGET_VALUE_LOCKED, default=-1): probatio.Coerce(float),
    probatio.Optional(
        CONF_UNIT_OF_MEASUREMENT, default=UnitOfTemperature.CELSIUS
    ): probatio.In(UnitOfTemperature.CELSIUS, UnitOfTemperature.FAHRENHEIT),
}


DOMAIN_DATA_COVER: VolDictType = {
    probatio.Required(CONF_MOTOR): probatio.All(
        probatio.Upper, probatio.In(MOTOR_PORTS)
    ),
    probatio.Optional(CONF_POSITIONING_MODE, default="none"): probatio.All(
        probatio.Upper, probatio.In(MOTOR_POSITIONING_MODES)
    ),
    probatio.Optional(CONF_REVERSE_TIME, default="rt1200"): probatio.All(
        probatio.Upper, probatio.In(MOTOR_REVERSE_TIMES)
    ),
}


DOMAIN_DATA_LIGHT: VolDictType = {
    probatio.Required(CONF_OUTPUT): probatio.All(
        probatio.Upper, probatio.In(OUTPUT_PORTS + RELAY_PORTS)
    ),
    probatio.Optional(CONF_DIMMABLE, default=False): probatio.Coerce(bool),
    probatio.Optional(CONF_TRANSITION, default=0): probatio.All(
        probatio.Coerce(float), probatio.Range(min=0.0, max=486.0)
    ),
}


DOMAIN_DATA_SCENE: VolDictType = {
    probatio.Required(CONF_REGISTER): probatio.All(
        probatio.Coerce(int), probatio.Range(0, 9)
    ),
    probatio.Required(CONF_SCENE): probatio.All(
        probatio.Coerce(int), probatio.Range(0, 9)
    ),
    probatio.Optional(CONF_OUTPUTS, default=[]): probatio.All(
        cv.ensure_list,
        [probatio.All(probatio.Upper, probatio.In(OUTPUT_PORTS + RELAY_PORTS))],
    ),
    probatio.Optional(CONF_TRANSITION, default=0): probatio.Any(
        probatio.All(probatio.Coerce(int), probatio.Range(min=0.0, max=486.0))
    ),
}

DOMAIN_DATA_SENSOR: VolDictType = {
    probatio.Required(CONF_SOURCE): probatio.All(
        probatio.Upper,
        probatio.In(
            VARIABLES + SETPOINTS + THRESHOLDS + S0_INPUTS + LED_PORTS + LOGICOP_PORTS
        ),
    ),
    probatio.Optional(CONF_UNIT_OF_MEASUREMENT, default="native"): probatio.All(
        probatio.Upper, probatio.In(VAR_UNITS)
    ),
}


DOMAIN_DATA_SWITCH: VolDictType = {
    probatio.Required(CONF_OUTPUT): probatio.All(
        probatio.Upper,
        probatio.In(OUTPUT_PORTS + RELAY_PORTS + SETPOINTS + KEYS),
    ),
}
