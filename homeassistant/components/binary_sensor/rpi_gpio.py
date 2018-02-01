"""
Support for binary sensor using RPi GPIO.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.rpi_gpio/
"""
import logging

import voluptuous as vol

import homeassistant.components.rpi_gpio as rpi_gpio
from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA)
from homeassistant.const import DEVICE_DEFAULT_NAME
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_BOUNCETIME = 'bouncetime'
CONF_INVERT_LOGIC = 'invert_logic'
CONF_PORTS = 'ports'
CONF_PULL_MODE = 'pull_mode'

DEFAULT_BOUNCETIME = 50
DEFAULT_INVERT_LOGIC = False
DEFAULT_PULL_MODE = 'UP'

DEPENDENCIES = ['rpi_gpio']

_SENSORS_SCHEMA = vol.Schema({
    cv.positive_int: cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_PORTS): _SENSORS_SCHEMA,
    vol.Optional(CONF_BOUNCETIME, default=DEFAULT_BOUNCETIME): cv.positive_int,
    vol.Optional(CONF_INVERT_LOGIC, default=DEFAULT_INVERT_LOGIC): cv.boolean,
    vol.Optional(CONF_PULL_MODE, default=DEFAULT_PULL_MODE): cv.string,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Raspberry PI GPIO devices."""
    pull_mode = config.get(CONF_PULL_MODE)
    bouncetime = config.get(CONF_BOUNCETIME)
    invert_logic = config.get(CONF_INVERT_LOGIC)

    binary_sensors = []
    ports = config.get('ports')
    for port_num, port_name in ports.items():
        binary_sensors.append(RPiGPIOBinarySensor(
            port_name, port_num, pull_mode, bouncetime, invert_logic))
    add_devices(binary_sensors, True)


class RPiGPIOBinarySensor(BinarySensorDevice):
    """Represent a binary sensor that uses Raspberry Pi GPIO."""

    def __init__(self, name, port, pull_mode, bouncetime, invert_logic):
        """Initialize the RPi binary sensor."""
        # pylint: disable=no-member
        self._name = name or DEVICE_DEFAULT_NAME
        self._port = port
        self._pull_mode = pull_mode
        self._bouncetime = bouncetime
        self._invert_logic = invert_logic
        self._state = None

        rpi_gpio.setup_input(self._port, self._pull_mode)

        def read_gpio(port):
            """Read state from GPIO."""
            self._state = rpi_gpio.read_input(self._port)
            self.schedule_update_ha_state()

        rpi_gpio.edge_detect(self._port, read_gpio, self._bouncetime)

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

    def update(self):
        """Update the GPIO state."""
        self._state = rpi_gpio.read_input(self._port)
