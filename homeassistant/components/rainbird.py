"""
Support for Rain Bird Irrigation system LNK WiFi Module.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/rainbird/
"""

import logging

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.exceptions import PlatformNotReady
from homeassistant.const import (CONF_HOST, CONF_PASSWORD)

REQUIREMENTS = ['pyrainbird==0.1.2']

DATA_RAINBIRD = 'rainbird'
DOMAIN = 'rainbird'
_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up Rain Bird componenent."""
    conf = config[DOMAIN]
    server = conf.get(CONF_HOST)
    password = conf.get(CONF_PASSWORD)

    from pyrainbird import RainbirdController
    controller = RainbirdController(_LOGGER)
    controller.setConfig(server, password)

    _LOGGER.debug("Rain Bird Controller set to " + str(server))

    initialstatus = controller.currentIrrigation()
    if initialstatus == -1:
        _LOGGER.error("Error getting state. Possible configuration issues")
        raise PlatformNotReady
    else:
        _LOGGER.debug("Initialized Rain Bird Controller")

    hass.data[DATA_RAINBIRD] = controller
    return True
