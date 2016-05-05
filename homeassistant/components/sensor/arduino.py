"""
Support for getting information from Arduino pins.

Only analog pins are supported.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.arduino/
"""
import logging

import homeassistant.components.arduino as arduino
from homeassistant.const import DEVICE_DEFAULT_NAME
from homeassistant.helpers.entity import Entity

DEPENDENCIES = ['arduino']
_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Arduino platform."""
    # Verify that the Arduino board is present
    if arduino.BOARD is None:
        _LOGGER.error('A connection has not been made to the Arduino board.')
        return False

    sensors = []
    pins = config.get('pins')
    for pinnum, pin in pins.items():
        if pin.get('name'):
            sensors.append(ArduinoSensor(pin.get('name'),
                                         pinnum,
                                         'analog'))
    add_devices(sensors)


class ArduinoSensor(Entity):
    """Representation of an Arduino Sensor."""

    def __init__(self, name, pin, pin_type):
        """Initialize the sensor."""
        self._pin = pin
        self._name = name or DEVICE_DEFAULT_NAME
        self.pin_type = pin_type
        self.direction = 'in'
        self._value = None

        arduino.BOARD.set_mode(self._pin, self.direction, self.pin_type)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._value

    @property
    def name(self):
        """Get the name of the sensor."""
        return self._name

    def update(self):
        """Get the latest value from the pin."""
        self._value = arduino.BOARD.get_analog_inputs()[self._pin][1]
