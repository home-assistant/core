"""
Local support for Insteon.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/insteon_local/
"""
import logging
import os

import requests
import voluptuous as vol

from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_TIMEOUT, CONF_USERNAME)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform

REQUIREMENTS = ['insteonlocal==0.53']

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 25105
DEFAULT_TIMEOUT = 10
DOMAIN = 'insteon_local'

INSTEON_CACHE = '.insteon_local_cache'

INSTEON_PLATFORMS = [
    'light',
    'switch',
    'fan',
]

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the local Insteon hub."""
    from insteonlocal.Hub import Hub

    conf = config[DOMAIN]
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)
    host = conf.get(CONF_HOST)
    port = conf.get(CONF_PORT)
    timeout = conf.get(CONF_TIMEOUT)

    try:
        if not os.path.exists(hass.config.path(INSTEON_CACHE)):
            os.makedirs(hass.config.path(INSTEON_CACHE))

        insteonhub = Hub(host, username, password, port, timeout, _LOGGER,
                         hass.config.path(INSTEON_CACHE))

        # Check for successful connection
        insteonhub.get_buffer_status()
    except requests.exceptions.ConnectTimeout:
        _LOGGER.error("Could not connect", exc_info=True)
        return False
    except requests.exceptions.ConnectionError:
        _LOGGER.error("Could not connect", exc_info=True)
        return False
    except requests.exceptions.RequestException:
        if insteonhub.http_code == 401:
            _LOGGER.error("Bad username or password for Insteon_local hub")
        else:
            _LOGGER.error("Error on Insteon_local hub check", exc_info=True)
        return False

    linked = insteonhub.get_linked()

    hass.data['insteon_local'] = insteonhub

    for insteon_platform in INSTEON_PLATFORMS:
        load_platform(hass, insteon_platform, DOMAIN, {'linked': linked},
                      config)

    return True
