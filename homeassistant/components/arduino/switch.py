"""Support for switching Arduino pins on and off."""
import logging

import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchDevice
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_PINS = "pins"
CONF_TYPE = "digital"
CONF_NEGATE = "negate"
CONF_INITIAL = "initial"

PIN_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_INITIAL, default=False): cv.boolean,
        vol.Optional(CONF_NEGATE, default=False): cv.boolean,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_PINS, default={}): vol.Schema({cv.positive_int: PIN_SCHEMA})}
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Arduino platform."""
    board = hass.data[DOMAIN]

    pins = config[CONF_PINS]

    switches = []
    for pinnum, pin in pins.items():
        switches.append(ArduinoSwitch(pinnum, pin, board))
    add_entities(switches)


class ArduinoSwitch(SwitchDevice):
    """Representation of an Arduino switch."""

    def __init__(self, pin, options, board):
        """Initialize the Pin."""
        self._pin = pin
        self._name = options[CONF_NAME]
        self.pin_type = CONF_TYPE
        self.direction = "out"

        self._state = options[CONF_INITIAL]

        if options[CONF_NEGATE]:
            self.turn_on_handler = board.set_digital_out_low
            self.turn_off_handler = board.set_digital_out_high
        else:
            self.turn_on_handler = board.set_digital_out_high
            self.turn_off_handler = board.set_digital_out_low

        board.set_mode(self._pin, self.direction, self.pin_type)
        (self.turn_on_handler if self._state else self.turn_off_handler)(pin)

    @property
    def name(self):
        """Get the name of the pin."""
        return self._name

    @property
    def is_on(self):
        """Return true if pin is high/on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the pin to high/on."""
        self._state = True
        self.turn_on_handler(self._pin)

    def turn_off(self, **kwargs):
        """Turn the pin to low/off."""
        self._state = False
        self.turn_off_handler(self._pin)
