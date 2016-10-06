"""
Support for switching Arduino pins on and off.

So far only digital pins are supported.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.arduino/
"""
import logging

import voluptuous as vol

import homeassistant.components.arduino as arduino
from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv

DEPENDENCIES = ['arduino']

_LOGGER = logging.getLogger(__name__)

CONF_PINS = 'pins'
CONF_TYPE = 'digital'
CONF_NEGATE = 'negate'
CONF_INITIAL = 'initial'

PIN_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_INITIAL, default=False): cv.boolean,
    vol.Optional(CONF_NEGATE, default=False): cv.boolean,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_PINS, default={}):
        vol.Schema({cv.positive_int: PIN_SCHEMA}),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Arduino platform."""
    # Verify that Arduino board is present
    if arduino.BOARD is None:
        _LOGGER.error("A connection has not been made to the Arduino board")
        return False

    pins = config.get(CONF_PINS)

    switches = []
    for pinnum, pin in pins.items():
        switches.append(ArduinoSwitch(pinnum, pin))
    add_devices(switches)


class ArduinoSwitch(SwitchDevice):
    """Representation of an Arduino switch."""

    def __init__(self, pin, options):
        """Initialize the Pin."""
        self._pin = pin
        self._name = options.get(CONF_NAME)
        self.pin_type = CONF_TYPE
        self.direction = 'out'

        self._state = options.get(CONF_INITIAL)

        if options.get(CONF_NEGATE):
            self.turn_on_handler = arduino.BOARD.set_digital_out_low
            self.turn_off_handler = arduino.BOARD.set_digital_out_high
        else:
            self.turn_on_handler = arduino.BOARD.set_digital_out_high
            self.turn_off_handler = arduino.BOARD.set_digital_out_low

        arduino.BOARD.set_mode(self._pin, self.direction, self.pin_type)
        (self.turn_on_handler if self._state else self.turn_off_handler)(pin)

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
        self.turn_on_handler(self._pin)

    def turn_off(self):
        """Turn the pin to low/off."""
        self._state = False
        self.turn_off_handler(self._pin)
