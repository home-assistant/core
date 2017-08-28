"""
Support for Rain Bird Irrigation system LNK WiFi Module.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/rainbird/
"""

import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity import Entity
from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD)

REQUIREMENTS = ['pyrainbird==0.0.7']

DOMAIN = 'rainbird'

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Rain Bird component."""
    server = config[DOMAIN].get(CONF_HOST)
    password = config[DOMAIN].get(CONF_PASSWORD)
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    from pyrainbird import RainbirdController

    controller = RainbirdController(_LOGGER)
    controller.setConfig(server, password)
    _LOGGER.info("Rain Bird Controller set to " + str(server))

    rbdevice = RainbirdDevice(hass, controller)
    hass.data["DATA_RAINBIRD"] = rbdevice

    initialstatus = rbdevice.update()
    if initialstatus == -1:
        _LOGGER.error("Error getting state. Possible configuration issues")
        raise PlatformNotReady
    else:
        _LOGGER.info("Initialized Rain Bird Controller")

    entities = []
    entities.append(rbdevice)
    component.add_entities(entities)

    return True


class RainbirdDevice(Entity):
    """Rain Bird Device."""

    _state = -1

    def __init__(self, hass, controller):
        """Initialize the device."""
        self.hass = hass
        self.controller = controller
        self._name = "Rainbird_Controller"
        self._stations = {}

        # For automation purposes add 2 services
        def start_irrigation_call(call):
            """Start irrigation from service call."""
            station_id = call.data.get("station_id")
            duration = call.data.get("duration")
            if station_id and duration:
                self.start_irrigation(station_id, duration)
            else:
                _LOGGER.warning("Error in start_irrigation call. \
                    station_id and duration need to be set")

        def stop_irrigation_call(call):
            """Start irrigation from service call."""
            self.stop_irrigation()

        hass.services.register(DOMAIN, 'start_irrigation',
                               start_irrigation_call)
        hass.services.register(DOMAIN, 'stop_irrigation',
                               stop_irrigation_call)

    def should_poll(self):
        """Return True if entity has to be polled for state."""
        return True

    @property
    def name(self):
        """Get the name of the device."""
        return self._name

    def available(self):
        """Return True if entity is available."""
        return self._state != -1

    @property
    def state(self):
        """Return the state of the entity."""
        return self._state

    def start_irrigation(self, station_id, duration):
        """
        Start Irrigation command towards Rain Bird LNK WiFi stick.

        @param call: should be a home assistant call object with data
        station for Zone to sprinkle and duration for the time
        """
        _LOGGER.info("Requesting irrigation for " +
                     str(station_id) + " duration " + str(duration))
        result = self.controller.startIrrigation(
            int(station_id), int(duration))
        if result == 1:
            _LOGGER.info("Irrigation started on " + str(station_id) +
                         " for " + str(duration))
        elif result == 0:
            _LOGGER.error("Error sending request")
        else:
            _LOGGER.error("Request was not acknowledged!")

    def stop_irrigation(self):
        """Stop the irrigation (if one is running)."""
        _LOGGER.info("Stop request irrigation")
        result = self.controller.stopIrrigation()
        if result == 1:
            _LOGGER.info("Stopped irrigation")
        elif result == 0:
            _LOGGER.error("Error sending request")
        else:
            _LOGGER.error("Request was not acknowledged!")

    def update(self):
        """
        Get current active station.

        @return: integer which station is active
        """
        _LOGGER.info("Request irrigation state")
        result = self.controller.currentIrrigation()
        if result < 0:
            _LOGGER.error("Error sending request")
            return -1
        self._state = result
