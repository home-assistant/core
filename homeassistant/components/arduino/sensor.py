"""Support for getting information from Arduino pins."""
import logging
from threading import Timer

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_MODE, CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_PINS = "pins"
CONF_TYPE = "analog"
PIN_MODE = 0  # This is the PyMata Pin MODE = ANALOG = 2 and DIGITAL = 0x20:
PIN_NUMBER = 1
DATA_VALUE = 2

PIN_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_MODE, default="analog"): vol.In(["analog", "digital"]),
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
        pin_type = pin.get("mode")
        if not pin_type:
            pin_type = CONF_TYPE
        sensors.append(ArduinoSensor(pin.get(CONF_NAME), pinnum, pin_type, board))
    add_entities(sensors)


class ArduinoSensor(Entity):
    """Representation of an Arduino Sensor."""

    def __init__(self, name, pin, pin_type, board):
        """Initialize the sensor."""
        self._pin = pin
        self._name = name
        self.pin_type = pin_type
        self.direction = "in"
        self._value = None

        board.set_mode(self._pin, self.direction, self.pin_type, self.cb_value_changed)
        self._board = board

        t = Timer(20.0, self.set_initial_value)
        t.start()

    @property
    def should_poll(self):
        """No need to poll. Sensor receives the update from PyMata."""
        return False

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._value

    @property
    def name(self):
        """Get the name of the sensor."""
        return self._name

    def cb_value_changed(self, data):
        """Set the value from the data passed in the callback."""
        self._value = data[DATA_VALUE]
        self.async_write_ha_state()

    def set_initial_value(self):
        """Set the initial value to zero if no value has been received yet."""
        if self._value is None:
            self._value = 0
            self.async_write_ha_state()
