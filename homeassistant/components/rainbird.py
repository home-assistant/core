"""
Support for Rain Bird Irrigation system LNK WiFi Module.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/rainbird/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (CONF_HOST, CONF_PASSWORD)

REQUIREMENTS = ['pyrainbird==0.1.3']

_LOGGER = logging.getLogger(__name__)

DATA_RAINBIRD = 'rainbird'
DOMAIN = 'rainbird'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Rain Bird component."""
    conf = config[DOMAIN]
    server = conf.get(CONF_HOST)
    password = conf.get(CONF_PASSWORD)

    from pyrainbird import RainbirdController
    controller = RainbirdController()
    controller.setConfig(server, password)

    _LOGGER.debug("Rain Bird Controller set to: %s", server)

    initial_status = controller.currentIrrigation()
    if initial_status == -1:
        _LOGGER.error("Error getting state. Possible configuration issues")
        return False

    hass.data[DATA_RAINBIRD] = controller
    return True
