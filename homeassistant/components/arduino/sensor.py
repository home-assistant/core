"""Support for getting information from Arduino analog pins."""
import asyncio
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_PINS = "pins"
CONF_DIFF = "differential"

PIN_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_DIFF, default=0): cv.positive_int,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_PINS): vol.Schema({cv.positive_int: PIN_SCHEMA})}
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Arduino platform."""
    board = hass.data[DOMAIN]

    pins = config[CONF_PINS]

    sensors = []
    for pinnum, pin in pins.items():
        sensors.append(ArduinoSensor(pinnum, pin, board))
    add_entities(sensors)


class ArduinoSensor(Entity):
    """Representation of an Arduino Sensor."""

    def __init__(self, pin, options, board):
        """Initialize the sensor."""
        self._pin = pin
        self._name = options[CONF_NAME]
        self._diff = options[CONF_DIFF]
        self._value = None
        self._board = board

        if self._diff == 0:
            self._board.set_pin_mode_analog_input(self._pin)
        else:
            self._board.set_pin_mode_analog_input(self._pin, self._cb, self._diff)
            self._value = self._board.analog_read(self._pin)[0]
            self.async_write_ha_state()

    def _cb(self, data):
        self._value = data[2]
        self.async_write_ha_state()

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._value

    @property
    def name(self):
        """Get the name of the sensor."""
        return self._name

    @property
    def should_poll(self):
        """Return whether HA should poll for data updates."""
        return self._diff == 0

    def update(self):
        """Get the latest value from the pin."""
        self._value = self._board.analog_read(self._pin)[0]
