"""
Allows to configure a switch using BBB GPIO.

Switch example for two GPIOs pins P9_12 and P9_42.
GPIO pin name support GPIOxxx and Px_x format.

switch:
  - platform: bbb_gpio
    ports:
      GPIO0_7: LED Red
      P9_12: LED Green
"""
import logging

import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA
import homeassistant.components.bbb_gpio as bbb_gpio
from homeassistant.const import DEVICE_DEFAULT_NAME
from homeassistant.helpers.entity import ToggleEntity
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['bbb_gpio']

CONF_PULL_MODE = 'pull_mode'
CONF_PORTS = 'ports'
CONF_INVERT_LOGIC = 'invert_logic'

DEFAULT_INVERT_LOGIC = False

_SWITCHES_SCHEMA = vol.Schema({
    cv.string: cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_PORTS): _SWITCHES_SCHEMA,
    vol.Optional(CONF_INVERT_LOGIC, default=DEFAULT_INVERT_LOGIC): cv.boolean,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Beaglebone GPIO devices."""
    invert_logic = config.get(CONF_INVERT_LOGIC)

    switches = []
    ports = config.get(CONF_PORTS)
    for port, name in ports.items():
        switches.append(BBBGPIOSwitch(name, port, invert_logic))
    add_devices(switches)


class BBBGPIOSwitch(ToggleEntity):
    """Representation of a  Beaglebone GPIO."""

    def __init__(self, name, port, invert_logic):
        """Initialize the pin."""
        self._name = name or DEVICE_DEFAULT_NAME
        self._port = port
        self._invert_logic = invert_logic
        self._state = False
        bbb_gpio.setup_output(self._port)
        bbb_gpio.write_output(self._port, 1 if self._invert_logic else 0)

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

    def turn_on(self):
        """Turn the device on."""
        bbb_gpio.write_output(self._port, 0 if self._invert_logic else 1)
        self._state = True
        self.update_ha_state()

    def turn_off(self):
        """Turn the device off."""
        bbb_gpio.write_output(self._port, 1 if self._invert_logic else 0)
        self._state = False
        self.update_ha_state()
