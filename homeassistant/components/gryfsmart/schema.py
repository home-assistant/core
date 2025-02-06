"""Config schema for Gryf Smart Integration."""

import voluptuous as vol

from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_DEVICE_CLASS,
    CONF_ID,
    CONF_MODULE_COUNT,
    CONF_NAME,
    CONF_PORT,
    DOMAIN,
    PLATFORM_BINARY_SENSOR,
    PLATFORM_INPUT,
    PLATFORM_LIGHT,
    PLATFORM_PWM,
    PLATFORM_SWITCH,
)

STANDARD_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ID): cv.positive_int,
    }
)
DEVICE_CLASS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ID): cv.positive_int,
        vol.Optional(CONF_DEVICE_CLASS): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_PORT): cv.string,
                vol.Required(CONF_MODULE_COUNT): cv.positive_int,
                vol.Optional(PLATFORM_PWM): vol.All(cv.ensure_list, [STANDARD_SCHEMA]),
                vol.Optional(PLATFORM_LIGHT): vol.All(
                    cv.ensure_list, [STANDARD_SCHEMA]
                ),
                vol.Optional(PLATFORM_INPUT): vol.All(
                    cv.ensure_list, [STANDARD_SCHEMA]
                ),
                vol.Optional(PLATFORM_BINARY_SENSOR): vol.All(
                    cv.ensure_list, [DEVICE_CLASS_SCHEMA]
                ),
                vol.Optional(PLATFORM_SWITCH): vol.All(
                    cv.ensure_list, [DEVICE_CLASS_SCHEMA]
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)
