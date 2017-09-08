"""
Support for Rain Bird Irrigation system LNK WiFi Module.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/rainbird/
"""

import logging

import voluptuous as vol

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import (CONF_PLATFORM, CONF_SWITCHES, CONF_ZONE,
                                 CONF_FRIENDLY_NAME, CONF_TRIGGER_TIME,
                                 CONF_SCAN_INTERVAL, CONF_HOST, CONF_PASSWORD)
from homeassistant.helpers import config_validation as cv
from homeassistant.exceptions import PlatformNotReady

REQUIREMENTS = ['pyrainbird==0.0.9']

DOMAIN = 'rainbird'
_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): DOMAIN,
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_SWITCHES, default={}): vol.Schema({
        cv.string: {
            vol.Optional(CONF_FRIENDLY_NAME): cv.string,
            vol.Required(CONF_ZONE): cv.string,
            vol.Required(CONF_TRIGGER_TIME): cv.string,
            vol.Optional(CONF_SCAN_INTERVAL): cv.string,
        },
    }),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up Rain Bird switches over a Rain Bird controller."""
    server = config.get(CONF_HOST)
    password = config.get(CONF_PASSWORD)
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    from pyrainbird import RainbirdController

    controller = RainbirdController(_LOGGER)
    controller.setConfig(server, password)
    _LOGGER.info("Rain Bird Controller set to " + str(server))

    rbdevice = RainbirdDevice(hass, controller)
    initialstatus = rbdevice.update()
    if initialstatus == -1:
        _LOGGER.error("Error getting state. Possible configuration issues")
        raise PlatformNotReady
    else:
        _LOGGER.info("Initialized Rain Bird Controller")

    entities = []
    entities.append(rbdevice)
    component.add_entities(entities)

    devices = []
    for dev_id, switch in config.get(CONF_SWITCHES).items():
        devices.append(RainBirdSwitch(rbdevice, switch, dev_id))
    add_devices(devices)
    return True


class RainBirdSwitch(SwitchDevice):
    """Representation of a Rain Bird switch."""

    def __init__(self, rb, dev, dev_id):
        """Initialize a Rain Bird Switch Device."""
        self._rainbird = rb
        self._devid = dev_id
        self._zone = int(dev.get(CONF_ZONE))
        self._name = dev.get(CONF_FRIENDLY_NAME, "Sprinker %s" % self._zone)
        self._state = self.get_device_status()
        self._duration = dev.get(CONF_TRIGGER_TIME)
        self._attributes = {
            "duration": self._duration,
            "zone": self._zone
        }

    @property
    def device_state_attributes(self):
        """Return state attributes."""
        return self._attributes

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    @property
    def name(self):
        """Get the name of the switch."""
        return self._name

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self._state = True
        self._rainbird.start_irrigation(self._zone, self._duration)
        self._rainbird.setstate(self._zone)

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self._state = False
        self._rainbird.stop_irrigation()
        self._rainbird.setstate(0)

    def get_device_status(self):
        """Get the status of the switch from Rain Bird Controller."""
        return self._rainbird.state == self._zone

    def update(self):
        """Update switch status."""
        self._state = self.get_device_status()

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state


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

    def setstate(self, state):
        """Force set the current state value."""
        self._state = state

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
