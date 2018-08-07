"""
Support for binary sensor using the RPi GPIO Zero library.

This component can interact with both local GPIO pins and remote GPIO pins (via
(pigpio)[http://abyz.me.uk/rpi/pigpio].  Local pin configuration is identical
to the standard rpi_gpio component.  To connect to a remote `pigpio` daemon
use the `host` and `port` options, for example:

    binary_sensor:
      - platform: rpi_gpiozero
        host: 192.168.1.254
        ports:
          18: Front Door
          19: Rear Door

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.rpi_gpiozero/
"""
import logging
import threading

import voluptuous as vol

import homeassistant.components.rpi_gpiozero as rpi_gpiozero
from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA)
from homeassistant.const import DEVICE_DEFAULT_NAME
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_BOUNCETIME = 'bouncetime'
CONF_INVERT_LOGIC = 'invert_logic'
CONF_PORTS = 'ports'
CONF_PULL_MODE = 'pull_mode'
CONF_HOST = 'host'
CONF_PORT = 'port'

DEFAULT_BOUNCETIME = 50
DEFAULT_INVERT_LOGIC = False
DEFAULT_PULL_MODE = 'UP'
DEFAULT_HOST = ''
DEFAULT_PORT = 8888

DEPENDENCIES = ['rpi_gpiozero']

_SENSORS_SCHEMA = vol.Schema({
    cv.positive_int: cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_PORTS): _SENSORS_SCHEMA,
    vol.Optional(CONF_BOUNCETIME, default=DEFAULT_BOUNCETIME): cv.positive_int,
    vol.Optional(CONF_INVERT_LOGIC, default=DEFAULT_INVERT_LOGIC): cv.boolean,
    vol.Optional(CONF_PULL_MODE, default=DEFAULT_PULL_MODE): cv.string,
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.positive_int,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Raspberry PI GPIO devices."""
    pull_mode = config.get(CONF_PULL_MODE)
    bouncetime = config.get(CONF_BOUNCETIME)
    invert_logic = config.get(CONF_INVERT_LOGIC)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)

    binary_sensors = []
    ports = config.get('ports')
    for port_num, port_name in ports.items():
        binary_sensors.append(RPiGPIOZeroBinarySensor(
            port_name,
            port_num,
            pull_mode,
            bouncetime,
            invert_logic,
            (host, port)
        ))
    add_devices(binary_sensors, True)


class RPiGPIOZeroBinarySensor(BinarySensorDevice):
    """Represent a binary sensor that uses Raspberry Pi GPIO via gpiozero"""

    def __init__(self, name, port, pull_mode, bouncetime, invert_logic,
                 hostport):
        """Initialize the RPi gpiozero binary sensor."""
        # pylint: disable=no-member
        self._name = name or DEVICE_DEFAULT_NAME
        self._port = port
        self._pull_mode = pull_mode
        self._bouncetime = bouncetime
        self._invert_logic = invert_logic
        self._hostport = hostport
        self._state = None
        self._btn = None
        self._btn_lock = threading.Lock()

    @property
    def btn(self):
        self._btn_lock.acquire()
        try:
            if self._btn is None and self._hostport:

                _LOGGER.debug("creating button %s on port %s",
                              self._name, self._port)
                self._btn = rpi_gpiozero.setup_button(
                    self._port,
                    self._pull_mode,
                    self._bouncetime,
                    self._hostport
                )

                if self._btn is None:
                    _LOGGER.error("failed to create button %s on port %s",
                                  self._name, self._port)
                else:
                    def on_change(device):
                        """Read state from GPIO."""
                        self._state = device.is_pressed
                        _LOGGER.info("%s has changed to %s",
                                     self._name, self._state)
                        self.schedule_update_ha_state()

                    self._btn.when_pressed = on_change
                    self._btn.when_released = on_change
        finally:
            self._btn_lock.release()

        return self._btn

    @property
    def should_poll(self):
        """
        Polling isn't required for state changes, but it useful for tracking
        and restoring connectivity
        """
        return True

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return the state of the entity."""
        return self._state != self._invert_logic

    @property
    def available(self):
        return self.btn is not None

    def _reset(self):
        self._btn = None
        return self.btn

    def update(self):
        """Update the GPIO state."""
        _LOGGER.info("Updating %s", self._name)
        if self.btn:
            try:
                if self.btn.closed:
                    _LOGGER.exception("%s has been closed", self._name)
                    self._reset()
                else:
                    self._state = self.btn.is_pressed
            except:
                # If there are any errors during checking is_pressed
                # reset the _btn
                _LOGGER.exception("%s has failed to update", self._name)
                self._reset()
        else:
            self._state = False

        _LOGGER.info("%s has been updated to state %s",
                     self._name, self._state)
