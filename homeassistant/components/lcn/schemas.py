"""Schema definitions for LCN configuration and websockets api."""
import voluptuous as vol

from homeassistant.components.climate import DEFAULT_MAX_TEMP, DEFAULT_MIN_TEMP
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_BINARY_SENSORS,
    CONF_COVERS,
    CONF_HOST,
    CONF_LIGHTS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SENSORS,
    CONF_SWITCHES,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_USERNAME,
)
import homeassistant.helpers.config_validation as cv

from .const import (
    BINSENSOR_PORTS,
    CONF_CLIMATES,
    CONF_CONNECTIONS,
    CONF_DIM_MODE,
    CONF_DIMMABLE,
    CONF_LOCKABLE,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_MOTOR,
    CONF_OUTPUT,
    CONF_OUTPUTS,
    CONF_REGISTER,
    CONF_REVERSE_TIME,
    CONF_SCENE,
    CONF_SCENES,
    CONF_SETPOINT,
    CONF_SK_NUM_TRIES,
    CONF_SOURCE,
    CONF_TRANSITION,
    DIM_MODES,
    DOMAIN,
    KEYS,
    LED_PORTS,
    LOGICOP_PORTS,
    MOTOR_PORTS,
    MOTOR_REVERSE_TIME,
    OUTPUT_PORTS,
    RELAY_PORTS,
    S0_INPUTS,
    SETPOINTS,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    THRESHOLDS,
    VAR_UNITS,
    VARIABLES,
)
from .helpers import has_unique_host_names, is_address

#
# Domain data
#

DOMAIN_DATA_BINARY_SENSOR = {
    vol.Required(CONF_SOURCE): vol.All(
        vol.Upper, vol.In(SETPOINTS + KEYS + BINSENSOR_PORTS)
    ),
}


DOMAIN_DATA_CLIMATE = {
    vol.Required(CONF_SOURCE): vol.All(vol.Upper, vol.In(VARIABLES)),
    vol.Required(CONF_SETPOINT): vol.All(vol.Upper, vol.In(VARIABLES + SETPOINTS)),
    vol.Optional(CONF_MAX_TEMP, default=DEFAULT_MAX_TEMP): vol.Coerce(float),
    vol.Optional(CONF_MIN_TEMP, default=DEFAULT_MIN_TEMP): vol.Coerce(float),
    vol.Optional(CONF_LOCKABLE, default=False): vol.Coerce(bool),
    vol.Optional(CONF_UNIT_OF_MEASUREMENT, default=TEMP_CELSIUS): vol.In(
        TEMP_CELSIUS, TEMP_FAHRENHEIT
    ),
}


DOMAIN_DATA_COVER = {
    vol.Required(CONF_MOTOR): vol.All(vol.Upper, vol.In(MOTOR_PORTS)),
    vol.Optional(CONF_REVERSE_TIME, default="rt1200"): vol.All(
        vol.Upper, vol.In(MOTOR_REVERSE_TIME)
    ),
}


DOMAIN_DATA_LIGHT = {
    vol.Required(CONF_OUTPUT): vol.All(vol.Upper, vol.In(OUTPUT_PORTS + RELAY_PORTS)),
    vol.Optional(CONF_DIMMABLE, default=False): vol.Coerce(bool),
    vol.Optional(CONF_TRANSITION, default=0): vol.All(
        vol.Coerce(float), vol.Range(min=0.0, max=486.0), lambda value: value * 1000
    ),
}


DOMAIN_DATA_SCENE = {
    vol.Required(CONF_REGISTER): vol.All(vol.Coerce(int), vol.Range(0, 9)),
    vol.Required(CONF_SCENE): vol.All(vol.Coerce(int), vol.Range(0, 9)),
    vol.Optional(CONF_OUTPUTS, default=[]): vol.All(
        cv.ensure_list, [vol.All(vol.Upper, vol.In(OUTPUT_PORTS + RELAY_PORTS))]
    ),
    vol.Optional(CONF_TRANSITION, default=None): vol.Any(
        vol.All(
            vol.Coerce(int),
            vol.Range(min=0.0, max=486.0),
            lambda value: value * 1000,
        ),
        None,
    ),
}

DOMAIN_DATA_SENSOR = {
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


DOMAIN_DATA_SWITCH = {
    vol.Required(CONF_OUTPUT): vol.All(vol.Upper, vol.In(OUTPUT_PORTS + RELAY_PORTS)),
}

#
# Configuration
#

DOMAIN_DATA_BASE = {
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_ADDRESS): is_address,
}

BINARY_SENSORS_SCHEMA = vol.Schema({**DOMAIN_DATA_BASE, **DOMAIN_DATA_BINARY_SENSOR})

CLIMATES_SCHEMA = vol.Schema({**DOMAIN_DATA_BASE, **DOMAIN_DATA_CLIMATE})

COVERS_SCHEMA = vol.Schema({**DOMAIN_DATA_BASE, **DOMAIN_DATA_COVER})

LIGHTS_SCHEMA = vol.Schema({**DOMAIN_DATA_BASE, **DOMAIN_DATA_LIGHT})

SCENES_SCHEMA = vol.Schema({**DOMAIN_DATA_BASE, **DOMAIN_DATA_SCENE})

SENSORS_SCHEMA = vol.Schema({**DOMAIN_DATA_BASE, **DOMAIN_DATA_SENSOR})

SWITCHES_SCHEMA = vol.Schema({**DOMAIN_DATA_BASE, **DOMAIN_DATA_SWITCH})

CONNECTION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT): cv.port,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SK_NUM_TRIES, default=0): cv.positive_int,
        vol.Optional(CONF_DIM_MODE, default="steps50"): vol.All(
            vol.Upper, vol.In(DIM_MODES)
        ),
        vol.Optional(CONF_NAME): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CONNECTIONS): vol.All(
                    cv.ensure_list, has_unique_host_names, [CONNECTION_SCHEMA]
                ),
                vol.Optional(CONF_BINARY_SENSORS): vol.All(
                    cv.ensure_list, [BINARY_SENSORS_SCHEMA]
                ),
                vol.Optional(CONF_CLIMATES): vol.All(cv.ensure_list, [CLIMATES_SCHEMA]),
                vol.Optional(CONF_COVERS): vol.All(cv.ensure_list, [COVERS_SCHEMA]),
                vol.Optional(CONF_LIGHTS): vol.All(cv.ensure_list, [LIGHTS_SCHEMA]),
                vol.Optional(CONF_SCENES): vol.All(cv.ensure_list, [SCENES_SCHEMA]),
                vol.Optional(CONF_SENSORS): vol.All(cv.ensure_list, [SENSORS_SCHEMA]),
                vol.Optional(CONF_SWITCHES): vol.All(cv.ensure_list, [SWITCHES_SCHEMA]),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)
