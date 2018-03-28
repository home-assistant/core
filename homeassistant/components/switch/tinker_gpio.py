#! usr/bin/python
#coding=utf-8

"""
Allows to configure a switch using TinkerBoard GPIO.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.tinker_gpio/
"""

from homeassistant.helpers.entity import ToggleEntity
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

import logging

from homeassistant.components.switch import PLATFORM_SCHEMA
import homeassistant.components.tinker_gpio as tinker_gpio
from homeassistant.const import (CONF_NAME)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'tinker_gpio'
CONF_PORTS = 'ports'
CONF_INVERT_LOGIC = 'invert_logic'

DEFAULT_INVERT_LOGIC = False

_SWITCHES_SCHEMA = vol.Schema({
    cv.positive_int: cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_PORTS): _SWITCHES_SCHEMA,
    vol.Optional(CONF_INVERT_LOGIC, default=DEFAULT_INVERT_LOGIC): cv.boolean,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the TinkerBoard GPIO devices."""
    invert_logic = config.get(CONF_INVERT_LOGIC)

    switches = []
    ports = config.get(CONF_PORTS)
    for port, name in ports.items():
        switches.append(TinkerGPIOSwitch(name, port, invert_logic))
    add_devices(switches)

class TinkerGPIOSwitch(ToggleEntity):
    """Representation of a TinkerBoard GPIO."""

    def __init__(self, name, port, invert_logic):
        """Initialize the pin."""
        self._name = name or CONF_NAME
        self._port = port
        self._invert_logic = invert_logic
        self._state = False
        tinker_gpio.setup_output(self._port)
        tinker_gpio.write_output(self._port, 1 if self._invert_logic else 0)

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the device on."""
        tinker_gpio.write_output(self._port, 0 if self._invert_logic else 1)
        self._state = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        tinker_gpio.write_output(self._port, 1 if self._invert_logic else 0)
        self._state = False
        self.schedule_update_ha_state()
