"""Config schema for Gryf Smart Integration."""

import voluptuous as vol

from homeassistant.helpers import config_validation as cv

from .const import CONF_ID, CONF_MODULE_COUNT, CONF_NAME, CONF_PORT, DOMAIN

STANDARD_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ID): cv.positive_int,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional("light"): vol.All(cv.ensure_list, [STANDARD_SCHEMA]),
                vol.Required(CONF_PORT): cv.string,
                vol.Optional(CONF_MODULE_COUNT): cv.positive_int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)
