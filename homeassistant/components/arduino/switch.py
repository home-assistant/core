"""Support for switching Arduino pins on and off."""
import logging

import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_PINS = "pins"
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


class ArduinoSwitch(SwitchEntity):
    """Representation of an Arduino switch."""

    def __init__(self, pin, options, board):
        """Initialize the Pin."""
        self._pin = pin
        self._name = options[CONF_NAME]
        self._negate = options[CONF_NEGATE]
        self._state = options[CONF_INITIAL]
        self._board = board

        self._board.set_pin_mode_digital_output(self._pin)
        self._update()

    @property
    def name(self):
        """Get the name of the pin."""
        return self._name

    @property
    def is_on(self):
        """Return true if pin is high/on."""
        return self._state

    def _update(self):
        self._board.digital_write(self._pin, self._state ^ self._negate)

    def async_turn_on(self, **kwargs):
        """Turn the pin to high/on."""
        self._state = True
        self._update()

    def async_turn_off(self, **kwargs):
        """Turn the pin to low/off."""
        self._state = False
        self._update()
