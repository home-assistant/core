"""
Support for Rain Bird Irrigation system LNK WiFi Module.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/rainbird/
"""

import logging

import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.const import (CONF_PLATFORM, CONF_HOST, CONF_PASSWORD)

REQUIREMENTS = ['pyrainbird==0.1.1']

DATA_RAINBIRD = 'rainbird'

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_PLATFORM): DOMAIN,
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
})


def setup(hass, config):
     """Set up Rain Bird componenent."""
    server = config.get(CONF_HOST)
    password = config.get(CONF_PASSWORD)

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

    def hub_refresh(event_time):
        """Call Raincloud hub to refresh information."""
        _LOGGER.debug("Updating RainCloud Hub component.")
        hass.data[DATA_RAINCLOUD].data.update()
        dispatcher_send(hass, SIGNAL_UPDATE_RAINCLOUD)