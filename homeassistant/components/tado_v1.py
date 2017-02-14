"""
Support for the (unofficial) tado api.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/tado_v1/
"""

import logging
import urllib

import voluptuous as vol

from homeassistant.components.discovery import load_platform
from homeassistant.helpers import config_validation as cv
from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD)


_LOGGER = logging.getLogger(__name__)

DOMAIN = 'tado_v1'

REQUIREMENTS = ['https://github.com/wmalgadey/PyTado/archive/'
                '0.1.10.zip#'
                'PyTado==0.1.10']

TADO_V1_COMPONENTS = [
    'sensor', 'climate'
]

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME, default=''): cv.string,
        vol.Required(CONF_PASSWORD, default=''): cv.string
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Your controller/hub specific code."""
    username = config[DOMAIN][CONF_USERNAME]
    password = config[DOMAIN][CONF_PASSWORD]

    from PyTado.interface import Tado

    try:
        tado = Tado(username, password)
    except (RuntimeError, urllib.error.HTTPError):
        _LOGGER.error("Unable to connect to mytado with username and password")
        return False

    hass.data['Mytado'] = tado

    for component in TADO_V1_COMPONENTS:
        load_platform(hass, component, DOMAIN, {}, config)

    return True
