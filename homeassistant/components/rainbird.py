"""
Support for Rainbird Irrigation system WiFi LNK Module.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/rainbird/
"""

import logging
import voluptuous as vol
import homeassistant.helpers as helpers
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD)

REQUIREMENTS = ['pyrainbird==0.0.7']

DOMAIN = 'rainbird'
STATE_VAR = 'rainbird.activestation'

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Rainbird component."""
    server = config[DOMAIN].get(CONF_HOST)
    password = config[DOMAIN].get(CONF_PASSWORD)

    # RainbirdSetup
    from pyrainbird import RainbirdController

    controller = RainbirdController(_LOGGER)
    controller.setConfig(server, password)
    _LOGGER.info("Rainbird Controller set to " + str(server))

    def startirrigation(call):
        """
        Start Irrigation command towards Rainbird WiFi LNK stick.

        @param call: should be a home assistant call object with data
        station for Zone to sprinkle and duration for the time
        """
        station_id = call.data.get('station')
        duration = call.data.get('duration')
        _LOGGER.info("Requesting irrigation for " +
                     str(station_id) + " duration " + str(duration))
        result = controller.startIrrigation(station_id, duration)
        if result == 1:
            _LOGGER.info("Irrigation started on " + str(station_id) +
                         " for " + str(duration))
        elif result == 0:
            _LOGGER.error("Error sending request")
        else:
            _LOGGER.error("Request was not acknowledged!")

    def stopirrigation():
        """Stop the irrigation (if one is running)."""
        _LOGGER.info("Stop request irrigation")
        result = controller.stopIrrigation()
        if result == 1:
            _LOGGER.info("Stopped irrigation")
        elif result == 0:
            _LOGGER.error("Error sending request")
        else:
            _LOGGER.error("Request was not acknowledged!")

    def getirrigation():
        """
        Get current active station.

        @return: integer which station is active
        """
        _LOGGER.info("Request irrigation state")
        result = controller.currentIrrigation()
        if result < 0:
            _LOGGER.error("Error sending request")
            return -1

        return result
    initialstatus = getirrigation()
    hass.states.set(STATE_VAR, initialstatus)

    hass.services.register(DOMAIN, 'start_irrigation', startirrigation)
    hass.services.register(DOMAIN, 'stop_irrigation', stopirrigation)

    helpers.event.track_time_change(
        hass, lambda _: hass.states.set(STATE_VAR, getirrigation()),
        year=None, month=None, day=None,
        hour=None, minute=None, second=[00, 30]
    )
    _LOGGER.info("Initialized Rainbird Controller")

    return True
