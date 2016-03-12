"""
Support for switching Arduino pins on and off.

So far only digital pins are supported.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.arduino/
"""
import logging

import homeassistant.components.arduino as arduino
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import DEVICE_DEFAULT_NAME

DEPENDENCIES = ['arduino']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Arduino platform."""
    # Verify that Arduino board is present
    if arduino.BOARD is None:
        _LOGGER.error('A connection has not been made to the Arduino board.')
        return False

    switches = []
    pins = config.get('pins')
    for pinnum, pin in pins.items():
        if pin.get('name'):
            switches.append(ArduinoSwitch(pin.get('name'),
                                          pinnum,
                                          pin.get('type')))
    add_devices(switches)


class ArduinoSwitch(SwitchDevice):
    """Representation of an Arduino switch."""

    def __init__(self, name, pin, pin_type):
        """Initialize the Pin."""
        self._pin = pin
        self._name = name or DEVICE_DEFAULT_NAME
        self.pin_type = pin_type
        self.direction = 'out'
        self._state = False

        arduino.BOARD.set_mode(self._pin, self.direction, self.pin_type)

    @property
    def name(self):
        """Get the name of the pin."""
        return self._name

    @property
    def is_on(self):
        """Return true if pin is high/on."""
        return self._state

    def turn_on(self):
        """Turn the pin to high/on."""
        self._state = True
        arduino.BOARD.set_digital_out_high(self._pin)

    def turn_off(self):
        """Turn the pin to low/off."""
        self._state = False
        arduino.BOARD.set_digital_out_low(self._pin)
