"""
Support for the Netatmo devices (Weather Station and Welcome camera).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/netatmo/
"""
import logging
from urllib.error import HTTPError

import voluptuous as vol

from homeassistant.const import (
    CONF_API_KEY, CONF_PASSWORD, CONF_USERNAME)
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = [
    'https://github.com/jabesq/netatmo-api-python/archive/'
    'v0.5.0.zip#lnetatmo==0.5.0']

_LOGGER = logging.getLogger(__name__)

CONF_SECRET_KEY = 'secret_key'

DOMAIN = 'netatmo'

NETATMO_AUTH = None

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_SECRET_KEY): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Netatmo devices."""
    import lnetatmo

    global NETATMO_AUTH
    try:
        NETATMO_AUTH = lnetatmo.ClientAuth(
            config[DOMAIN][CONF_API_KEY], config[DOMAIN][CONF_SECRET_KEY],
            config[DOMAIN][CONF_USERNAME], config[DOMAIN][CONF_PASSWORD],
            'read_station read_camera access_camera')
    except HTTPError:
        _LOGGER.error("Unable to connect to Netatmo API")
        return False

    for component in 'camera', 'sensor':
        discovery.load_platform(hass, component, DOMAIN, {}, config)

    return True
