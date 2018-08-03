"""
Support for binary sensor using Beaglebone Black GPIO.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.bbb_gpio/
"""
import logging

import voluptuous as vol

from homeassistant.components import bbb_gpio
from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA)
from homeassistant.const import (DEVICE_DEFAULT_NAME, CONF_NAME)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['bbb_gpio']

CONF_PINS = 'pins'
CONF_BOUNCETIME = 'bouncetime'
CONF_INVERT_LOGIC = 'invert_logic'
CONF_PULL_MODE = 'pull_mode'

DEFAULT_BOUNCETIME = 50
DEFAULT_INVERT_LOGIC = False
DEFAULT_PULL_MODE = 'UP'

PIN_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_BOUNCETIME, default=DEFAULT_BOUNCETIME): cv.positive_int,
    vol.Optional(CONF_INVERT_LOGIC, default=DEFAULT_INVERT_LOGIC): cv.boolean,
    vol.Optional(CONF_PULL_MODE, default=DEFAULT_PULL_MODE):
        vol.In(['UP', 'DOWN'])
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_PINS, default={}):
        vol.Schema({cv.string: PIN_SCHEMA}),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Beaglebone Black GPIO devices."""
    pins = config.get(CONF_PINS)

    binary_sensors = []

    for pin, params in pins.items():
        binary_sensors.append(BBBGPIOBinarySensor(pin, params))
    add_devices(binary_sensors)


class BBBGPIOBinarySensor(BinarySensorDevice):
    """Representation of a binary sensor that uses Beaglebone Black GPIO."""

    def __init__(self, pin, params):
        """Initialize the Beaglebone Black binary sensor."""
        self._pin = pin
        self._name = params.get(CONF_NAME) or DEVICE_DEFAULT_NAME
        self._bouncetime = params.get(CONF_BOUNCETIME)
        self._pull_mode = params.get(CONF_PULL_MODE)
        self._invert_logic = params.get(CONF_INVERT_LOGIC)

        bbb_gpio.setup_input(self._pin, self._pull_mode)
        self._state = bbb_gpio.read_input(self._pin)

        def read_gpio(pin):
            """Read state from GPIO."""
            self._state = bbb_gpio.read_input(self._pin)
            self.schedule_update_ha_state()

        bbb_gpio.edge_detect(self._pin, read_gpio, self._bouncetime)

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return the state of the entity."""
        return self._state != self._invert_logic
