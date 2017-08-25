"""
Module for interacting with WiFi LNK module of the Rainbird Irrigation system

This project has no affiliation with Rainbird. This module works with the
Rainbird LNK WiFi Module. For more information see:
http://www.rainbird.com/landscape/products/controllers/LNK-WiFi.htm

This module communicates directly towards the IP Address of the WiFi module it
does not support the cloud. You can start/stop the irrigation and get the
currenltly active zone.

I'm not a Python developer, so sorry for the bad code. I've developed it to
control it from my domtica systems.
"""

import logging
import homeassistant.helpers as helpers

REQUIREMENTS = ['pyrainbird==0.0.7']

# Home Assistant Setup
DOMAIN = 'rainbird'
SERVER = ''
PASSWORD = ''
STATE_VAR = 'rainbird.activestation'

_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """
    Standard setup function Home Assistant
    @param hass: default homeassistant hass class
    @param config: default homeassistant config class
    """

    server = config[DOMAIN].get('stickip')
    password = config[DOMAIN].get('password')

    # RainbirdSetup
    from pyrainbird import RainbirdController

    controller = RainbirdController(_LOGGER)
    controller.setConfig(server, password)
    _LOGGER.info("Rainbird Controller set to " + str(server))

    def startirrigation(call):
        """
        Start Irrigation command towards Rainbird WiFi LNK stick
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
        """
        Stops the irrigation (if one is running)
        """

        _LOGGER.info("Stop request irrigation")
        result = controller.stopIrrigation()
        if result == 1:
            _LOGGER.info("Stopped irrigation")
            print("Success")
        elif result == 0:
            _LOGGER.error("Error sending request")
        else:
            _LOGGER.error("Request was not acknowledged!")

    def getirrigation():
        """
        Get current active station
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
