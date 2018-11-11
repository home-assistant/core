"""
Support for ecoal/esterownik.pl coal/wood boiler controller
"""


import voluptuous as vol

import homeassistant.helpers.config_validation as cv

from homeassistant.const import CONF_HOST

from homeassistant.components.light import PLATFORM_SCHEMA

CONF_LOGIN = "login"
DEFAULT_LOGIN = "admin"
CONF_PASSWORD = "password"
DEFAULT_PASSWORD = "admin"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_LOGIN,
                default=DEFAULT_LOGIN): cv.string,
    vol.Optional(CONF_PASSWORD,
                default=DEFAULT_PASSWORD): cv.string,

})
