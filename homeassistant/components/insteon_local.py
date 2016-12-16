"""
Local Support for Insteon.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/insteon_local/
"""
import logging

import voluptuous as vol

from homeassistant.const import (CONF_PASSWORD, CONF_USERNAME, CONF_HOST)
from homeassistant.helpers import discovery
from time import sleep
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['insteonlocal']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'insteon_local'
INSTEON_LOCAL = None

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Setup Insteon Hub component.

    This will automatically import associated lights.
    """

    from insteonlocal.Hub import Hub

    username = config[DOMAIN][CONF_USERNAME]
    password = config[DOMAIN][CONF_PASSWORD]
    host = config[DOMAIN][CONF_HOST]

    global INSTEON_LOCAL
    INSTEON_LOCAL = Hub(host, username, password)

    if INSTEON_LOCAL is None:
        _LOGGER.error("Could not connect to Insteon service")
        return False

    # sleep(5)
    discovery.load_platform(hass, 'light', DOMAIN, {}, config)
    discovery.load_platform(hass, 'switch', DOMAIN, {}, config)
    return True
