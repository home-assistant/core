"""
Support for Insteon Hub.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/insteon_hub/
"""
import logging

import voluptuous as vol

from homeassistant.const import (CONF_API_KEY, CONF_PASSWORD, CONF_USERNAME)
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['insteon_hub==0.4.5']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'insteon_hub'
INSTEON = None

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Insteon Hub component.

    This will automatically import associated lights.
    """
    _LOGGER.warning("Component disabled at request from Insteon. "
                    "For more information: https://goo.gl/zLJaic")
    return False
    # pylint: disable=unreachable
    import insteon

    username = config[DOMAIN][CONF_USERNAME]
    password = config[DOMAIN][CONF_PASSWORD]
    api_key = config[DOMAIN][CONF_API_KEY]

    global INSTEON
    INSTEON = insteon.Insteon(username, password, api_key)

    if INSTEON is None:
        _LOGGER.error("Could not connect to Insteon service")
        return False

    discovery.load_platform(hass, 'light', DOMAIN, {}, config)

    return True
