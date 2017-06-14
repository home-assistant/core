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

REQUIREMENTS = ['insteonlocal==0.52']

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 25105
DEFAULT_TIMEOUT = 10
DOMAIN = 'insteon_local'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Insteon Hub component.

    This will automatically import associated lights.
    """
    from insteonlocal.Hub import Hub

    conf = config[DOMAIN]
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)
    host = conf.get(CONF_HOST)
    port = conf.get(CONF_PORT)
    timeout = conf.get(CONF_TIMEOUT)

    try:
        if not os.path.exists(hass.config.path('.insteon_cache')):
            os.makedirs(hass.config.path('.insteon_cache'))

        insteonhub = Hub(host, username, password, port, timeout, _LOGGER,
                         hass.config.path('.insteon_cache'))

        # Check for successful connection
        insteonhub.get_buffer_status()
    except requests.exceptions.ConnectTimeout:
        _LOGGER.error("Error on insteon_local."
                      "Could not connect. Check config", exc_info=True)
        return False
    except requests.exceptions.ConnectionError:
        _LOGGER.error("Error on insteon_local. Could not connect."
                      "Check config", exc_info=True)
        return False
    except requests.exceptions.RequestException:
        if insteonhub.http_code == 401:
            _LOGGER.error("Bad user/pass for insteon_local hub")
            return False
        else:
            _LOGGER.error("Error on insteon_local hub check", exc_info=True)
            return False

    hass.data['insteon_local'] = insteonhub

    return True
