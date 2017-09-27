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
    CONF_PASSWORD, CONF_USERNAME, CONF_HOST, CONF_PORT, CONF_TIMEOUT)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform

REQUIREMENTS = ['insteonlocal==0.53']

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 25105
DEFAULT_TIMEOUT = 10
DOMAIN = 'insteon_local'

INSTEON_CACHE = '.insteon_local.cache'

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
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int
    })
def setup(hass, config):
    from insteonlocal.Hub import Hub

    username = config[DOMAIN].get(CONF_USERNAME)
    password = config[DOMAIN].get(CONF_PASSWORD)
    host = config[DOMAIN].get(CONF_HOST)
    port = config[DOMAIN].get(CONF_PORT)
    timeout = config[DOMAIN].get(CONF_TIMEOUT)

    _LOGGER.info("Initializing Insteon Local")

    try:
        if not os.path.exists(hass.config.path(INSTEON_CACHE)):
            os.makedirs(hass.config.path(INSTEON_CACHE))

        insteonhub = Hub(host, username, password, port, timeout, _LOGGER, hass.config.path(INSTEON_CACHE))

        # Check for successful connection
        insteonhub.get_buffer_status()
    except requests.exceptions.ConnectTimeout:
        _LOGGER.error("Error on insteon_local. Could not connect. Check config", exc_info=True)
        return False
    except requests.exceptions.ConnectionError:
        _LOGGER.error("Error on insteon_local. Could not connect. Check config", exc_info=True)
        return False
    except requests.exceptions.RequestException:
        if insteonhub.http_code == 401:
            _LOGGER.error("Bad user/pass for insteon_local hub")
        else:
            _LOGGER.error("Error on insteon_local hub check", exc_info=True)
        return False

    linked = insteonhub.get_linked()

    hass.data['insteon_local'] = insteonhub

    for insteon_platform in INSTEON_PLATFORMS:
        _LOGGER.info("Load platform " + insteon_platform)
        load_platform(hass, insteon_platform, DOMAIN, {'linked': linked})

    return True

