""".

Support for Etherrain valves.

"""
import logging

import voluptuous as vol

from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.const import (CONF_COMMAND_ON, CONF_COMMAND_OFF)
import homeassistant.components.etherrain as er
import homeassistant.helpers.config_validation as cv


_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['etherrain']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_COMMAND_ON): cv.string,
    vol.Required(CONF_COMMAND_OFF): cv.string,
    vol.Required("valve_id"): cv.positive_int,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Etherrain irrigation platform."""
    on_state = config.get(CONF_COMMAND_ON)
    off_state = config.get(CONF_COMMAND_OFF)
    valve_id = config.get("valve_id")
    valve_name = config.get("name")
    _LOGGER.info("Setting up etherrain switch {0}".format(valve_id))

    add_devices([ERValveSwitches(valve_id, valve_name, on_state, off_state)])


class ERValveSwitches(SwitchDevice):
    """Representation of an Etherrain valve."""

    icon = 'mdi:record-rec'

    def __init__(self, valve_id, valve_name, on_state, off_state):
        """Initialize ERValveSwitches."""
        self._valve_id = valve_id
        self._valve_name = valve_name
        self._duration = 0
        self._on_state = on_state
        self._off_state = off_state
        self._state = None

    @property
    def name(self):
        """Get valve name."""
        return self._valve_name

    def update(self):
        """Update valve state."""
        state = er.get_state(self._valve_id)

        if state == 1:
            self._state = True
        else:
            self._state = False
        # _LOGGER.info("update etherrain switch {0} - {1}".format(
        # self._valve_id, self._state))

    @property
    def is_on(self):
        """Return valve state."""
        # _LOGGER.info("is_on: etherrain switch {0} - {1}".format(
        # self._valve_id, self._state))
        return self._state

    def turn_on(self):
        """Turn a valve on."""
        valve = {}
        valve["duration"] = 60
        valve["valve"] = self._valve_id
        valve["command"] = er.WATER_ON
        # _LOGGER.info("turn on etherrain switch {0}".format(self._valve_id))
        self._state = True
        er.change_state(valve)

    def turn_off(self):
        """Turn a valve off."""
        valve = {}
        valve["duration"] = 0
        valve["valve"] = 0
        valve["command"] = er.WATER_OFF
        self._state = False
        # _LOGGER.info("turn off etherrain switch {0}".format(self._valve_id))
        er.change_state(valve)
