"""
Support for binary sensor using RPi GPIO.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.rpi_gpio/
"""
import logging
import time

import voluptuous as vol

import homeassistant.components.rpi_gpio as rpi_gpio
from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA)
from homeassistant.const import DEVICE_DEFAULT_NAME
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_BOUNCETIME = 'bouncetime'  # ms
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
        self._retry_read_interval = 10  # ms

        rpi_gpio.setup_input(self._port, self._pull_mode)

        def read_gpio(port):
            """Read state from GPIO."""
            # NOTE: This is RPi.GPIO callback, so it is in separate thread,
            #       but also only one thread is used for callbacks,
            #       so it's safe to time.sleep() inside
            # NOTE: Not sure if const time interval between GPIO reads
            #       or divide _bouncetime  by const number of tries?
            retry_count = int(self._bouncetime / self._retry_read_interval)
            while retry_count >= 0:
                new_state = rpi_gpio.read_input(self._port)
                # Reading GPIO not always returns valid state
                # (noise? RPi.GPIO issue/race? )
                # Let's try few times during bouncetime
                # until we get expected result from GPIO
                if new_state != self._state:
                    break
                _LOGGER.debug("Different than expected state read "
                              "in edge detection handler. "
                              "Repating GPIO read in %d ms, retries left: %r",
                              self._retry_read_interval, retry_count)
                time.sleep(self._retry_read_interval / 1000.0)
                retry_count -= 1
            self._state = new_state
            self.schedule_update_ha_state()

        # As edge detection seems be reliable with RPi.GPIO==0.6.1
        # it would be best to use separate handlers
        # for raising and falling cases changing state of switch
        # without reading GPIO which proves to be unreliable/ noise affected:
        #        rpi_gpio.rising_edge_detect(self._port,
        #                                    rising_edge_handler,
        #                                    self._bouncetime)
        #        rpi_gpio.falling_edge_detect(self._port,
        #                                     falling_edge_handler,
        #                                     self._bouncetime)
        # Unfortunately we are not able to have separate handlers
        # for falling and rising edge due to:
        #     RuntimeError: Conflicting edge detection
        #                   already enabled for this GPIO channel
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
