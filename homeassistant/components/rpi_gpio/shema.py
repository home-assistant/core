"""Shema used by rpi_gpio."""
import voluptuous as vol

from homeassistant.components.rpi_gpio.const import (
    CONF_COVER,
    CONF_COVER_INVERT_RELAY,
    CONF_COVER_INVERT_STATE,
    CONF_COVER_LIST,
    CONF_COVER_RELAY_PIN,
    CONF_COVER_RELAY_TIME,
    CONF_COVER_STATE_PIN,
    CONF_COVER_STATE_PULL_MODE,
    CONF_LIGHT,
    CONF_LIGHT_BUTTON_BOUNCETIME_MILLIS,
    CONF_LIGHT_BUTTON_DOUBLE_CHECK_TIME_MILLIS,
    CONF_LIGHT_BUTTON_PIN,
    CONF_LIGHT_BUTTON_PULL_MODE,
    CONF_LIGHT_INVERT_BUTTON,
    CONF_LIGHT_INVERT_RELAY,
    CONF_LIGHT_LIST,
    CONF_LIGHT_RELAY_PIN,
    CONF_SENSOR,
    CONF_SENSOR_BOUNCETIME,
    CONF_SENSOR_INVERT_LOGIC,
    CONF_SENSOR_PORTS,
    CONF_SENSOR_PULL_MODE,
    CONF_SWITCH,
    CONF_SWITCH_INVERT_LOGIC,
    CONF_SWITCH_PORTS,
    DEFAULT_COVER_INVERT_RELAY,
    DEFAULT_COVER_INVERT_STATE,
    DEFAULT_COVER_RELAY_TIME,
    DEFAULT_COVER_STATE_PULL_MODE,
    DEFAULT_LIGHT_BUTTON_BOUNCETIME_MILLIS,
    DEFAULT_LIGHT_BUTTON_PULL_MODE,
    DEFAULT_LIGHT_DOUBLE_CHECK_TIME_MILLIS,
    DEFAULT_LIGHT_INVERT_BUTTON,
    DEFAULT_LIGHT_INVERT_RELAY,
    DEFAULT_SENSOR_BOUNCETIME,
    DEFAULT_SENSOR_INVERT_LOGIC,
    DEFAULT_SENSOR_PULL_MODE,
    DEFAULT_SWITCH_INVERT_LOGIC,
    DOMAIN,
)
from homeassistant.const import CONF_NAME
from homeassistant.helpers import config_validation as cv

_LIGHT_SHEMA = vol.All(
    cv.ensure_list,
    [
        vol.Schema(
            {
                vol.Required(CONF_NAME): cv.string,
                vol.Required(CONF_LIGHT_RELAY_PIN): cv.positive_int,
                vol.Required(CONF_LIGHT_BUTTON_PIN): cv.positive_int,
            }
        )
    ],
)

_CONFIG_SCHEMA_LIGHT = vol.Schema(
    {
        vol.Required(CONF_LIGHT_LIST): _LIGHT_SHEMA,
        vol.Optional(
            CONF_LIGHT_BUTTON_PULL_MODE, default=DEFAULT_LIGHT_BUTTON_PULL_MODE
        ): cv.string,
        vol.Optional(
            CONF_LIGHT_BUTTON_BOUNCETIME_MILLIS,
            default=DEFAULT_LIGHT_BUTTON_BOUNCETIME_MILLIS,
        ): cv.positive_int,
        vol.Optional(
            CONF_LIGHT_BUTTON_DOUBLE_CHECK_TIME_MILLIS,
            default=DEFAULT_LIGHT_DOUBLE_CHECK_TIME_MILLIS,
        ): cv.positive_int,
        vol.Optional(
            CONF_LIGHT_INVERT_BUTTON, default=DEFAULT_LIGHT_INVERT_BUTTON
        ): cv.boolean,
        vol.Optional(
            CONF_LIGHT_INVERT_RELAY, default=DEFAULT_LIGHT_INVERT_RELAY
        ): cv.boolean,
    }
)
_SENSORS_SCHEMA = vol.Schema({cv.positive_int: cv.string})
_CONFIG_SCHEMA_SENSOR = vol.Schema(
    {
        vol.Required(CONF_SENSOR_PORTS): _SENSORS_SCHEMA,
        vol.Optional(
            CONF_SENSOR_BOUNCETIME, default=DEFAULT_SENSOR_BOUNCETIME
        ): cv.positive_int,
        vol.Optional(
            CONF_SENSOR_INVERT_LOGIC, default=DEFAULT_SENSOR_INVERT_LOGIC
        ): cv.boolean,
        vol.Optional(
            CONF_SENSOR_PULL_MODE, default=DEFAULT_SENSOR_PULL_MODE
        ): cv.string,
    }
)

_COVERS_SCHEMA = vol.All(
    cv.ensure_list,
    [
        vol.Schema(
            {
                CONF_NAME: cv.string,
                CONF_COVER_RELAY_PIN: cv.positive_int,
                CONF_COVER_STATE_PIN: cv.positive_int,
            }
        )
    ],
)

_CONFIG_SCHEMA_COVER = vol.Schema(
    {
        vol.Required(CONF_COVER_LIST): _COVERS_SCHEMA,
        vol.Optional(
            CONF_COVER_STATE_PULL_MODE, default=DEFAULT_COVER_STATE_PULL_MODE
        ): cv.string,
        vol.Optional(
            CONF_COVER_RELAY_TIME, default=DEFAULT_COVER_RELAY_TIME
        ): cv.positive_int,
        vol.Optional(
            CONF_COVER_INVERT_STATE, default=DEFAULT_COVER_INVERT_STATE
        ): cv.boolean,
        vol.Optional(
            CONF_COVER_INVERT_RELAY, default=DEFAULT_COVER_INVERT_RELAY
        ): cv.boolean,
    }
)

_SWITCHES_SCHEMA = vol.Schema({cv.positive_int: cv.string})

_CONFIG_SCHEMA_SWITCH = vol.Schema(
    {
        vol.Required(CONF_SWITCH_PORTS): _SWITCHES_SCHEMA,
        vol.Optional(
            CONF_SWITCH_INVERT_LOGIC, default=DEFAULT_SWITCH_INVERT_LOGIC
        ): cv.boolean,
    }
)

RPI_GPIO_CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_SWITCH): _CONFIG_SCHEMA_SWITCH,
                vol.Optional(CONF_COVER): _CONFIG_SCHEMA_COVER,
                vol.Optional(CONF_SENSOR): _CONFIG_SCHEMA_SENSOR,
                vol.Optional(CONF_LIGHT): _CONFIG_SCHEMA_LIGHT,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)
