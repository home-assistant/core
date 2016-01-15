"""
homeassistant.components.sensor.rpi_gpio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Allows to configure a binary state sensor using RPi GPIO.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.rpi_gpio/
"""

import logging
from homeassistant.components.binary_sensor.rpi_gpio import RPiGPIOBinarySensor

DEFAULT_PULL_MODE = "UP"
DEFAULT_BOUNCETIME = 50
DEFAULT_VALUE_HIGH = "HIGH"
DEFAULT_VALUE_LOW = "LOW"

DEPENDENCIES = ['rpi_gpio']
_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the Raspberry PI GPIO ports. """

    pull_mode = config.get('pull_mode', DEFAULT_PULL_MODE)
    bouncetime = config.get('bouncetime', DEFAULT_BOUNCETIME)
    value_high = config.get('value_high', DEFAULT_VALUE_HIGH)
    value_low = config.get('value_low', DEFAULT_VALUE_LOW)

    sensors = []
    ports = config.get('ports')
    for port, name in ports.items():
        sensors.append(RPiGPIOSensor(
            name, port, pull_mode, bouncetime,
            value_high, value_low))
    add_devices(sensors)


# pylint: disable=too-many-arguments, too-many-instance-attributes
class RPiGPIOSensor(RPiGPIOBinarySensor):
    """ Sets up the Raspberry PI GPIO ports. """
    def __init__(self, name, port, pull_mode, bouncetime,
                 value_high, value_low):

        self._value_high = value_high
        self._value_low = value_low
        super().__init__(name, port, pull_mode, bouncetime, False)

    @property
    def state(self):
        """ Returns the state of the entity. """
        if self._state != self._invert_logic:
            return self._value_high
        else:
            return self._value_low
