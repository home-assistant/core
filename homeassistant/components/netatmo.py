"""
Support for the Netatmo devices (Weather Station and Welcome camera).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/netatmo/
"""
import logging
from urllib.error import HTTPError
from homeassistant.const import (
    CONF_API_KEY, CONF_PASSWORD, CONF_USERNAME)
from homeassistant.helpers import validate_config, discovery

REQUIREMENTS = [
    'https://github.com/jabesq/netatmo-api-python/archive/'
    'v0.5.0.zip#lnetatmo==0.5.0']

_LOGGER = logging.getLogger(__name__)

CONF_SECRET_KEY = 'secret_key'

DOMAIN = "netatmo"
NETATMO_AUTH = None

_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """Setup the Netatmo devices."""
    if not validate_config(config,
                           {DOMAIN: [CONF_API_KEY,
                                     CONF_USERNAME,
                                     CONF_PASSWORD,
                                     CONF_SECRET_KEY]},
                           _LOGGER):
        return None

    import lnetatmo

    global NETATMO_AUTH
    try:
        NETATMO_AUTH = lnetatmo.ClientAuth(config[DOMAIN][CONF_API_KEY],
                                           config[DOMAIN][CONF_SECRET_KEY],
                                           config[DOMAIN][CONF_USERNAME],
                                           config[DOMAIN][CONF_PASSWORD],
                                           "read_station read_camera "
                                           "access_camera")
    except HTTPError:
        _LOGGER.error(
            "Connection error "
            "Please check your settings for NatAtmo API.")
        return False

    for component in 'camera', 'sensor':
        discovery.load_platform(hass, component, DOMAIN, {}, config)

    return True
