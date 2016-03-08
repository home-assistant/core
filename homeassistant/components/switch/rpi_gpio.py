"""
Allows to configure a switch using RPi GPIO.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.rpi_gpio/
"""

import logging

import homeassistant.components.rpi_gpio as rpi_gpio
from homeassistant.const import DEVICE_DEFAULT_NAME
from homeassistant.helpers.entity import ToggleEntity

DEFAULT_INVERT_LOGIC = False

DEPENDENCIES = ['rpi_gpio']
_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Raspberry PI GPIO devices."""
    invert_logic = config.get('invert_logic', DEFAULT_INVERT_LOGIC)

    switches = []
    ports = config.get('ports')
    for port, name in ports.items():
        switches.append(RPiGPIOSwitch(name, port, invert_logic))
    add_devices(switches)


class RPiGPIOSwitch(ToggleEntity):
    """Representation of a  Raspberry Pi GPIO."""

    def __init__(self, name, port, invert_logic):
        """Initialize the pin."""
        self._name = name or DEVICE_DEFAULT_NAME
        self._port = port
        self._invert_logic = invert_logic
        self._state = False
        rpi_gpio.setup_output(self._port)

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
        rpi_gpio.write_output(self._port, 0 if self._invert_logic else 1)
        self._state = True
        self.update_ha_state()

    def turn_off(self):
        """Turn the device off."""
        rpi_gpio.write_output(self._port, 1 if self._invert_logic else 0)
        self._state = False
        self.update_ha_state()
