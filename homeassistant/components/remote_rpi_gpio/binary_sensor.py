"""Support for binary sensor using RPi GPIO."""
import logging

import requests

from homeassistant.components import remote_rpi_gpio
from homeassistant.components.binary_sensor import (
    BinarySensorDevice)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['remote_rpi_gpio']


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Raspberry PI GPIO devices."""
    if discovery_info is None:
        return

    address = discovery_info['address']
    pull_mode = discovery_info['pull_mode']
    invert_logic = discovery_info['invert_logic']
    bouncetime = discovery_info['bouncetime']

    devices = []
    ports = discovery_info['binary_sensors']
    for port_num, port_name in ports.items():
        new_sensor = RemoteRPiGPIOBinarySensor(
            port_name, address, port_num, pull_mode, bouncetime, invert_logic)
        devices.append(new_sensor)
    add_entities(devices, True)


class RemoteRPiGPIOBinarySensor(BinarySensorDevice):
    """Represent a binary sensor that uses a Remote Raspberry Pi GPIO."""

    def __init__(self, name, address, port, pull_mode,
                 bouncetime, invert_logic):
        """Initialize the RPi binary sensor."""
        self._name = name
        self._address = address
        self._port = port
        self._pull_mode = pull_mode
        self._bouncetime = bouncetime
        self._invert_logic = invert_logic
        self._state = False
        self._button = None

        try:
            self._button = remote_rpi_gpio.setup_input(self._address,
                                                       self._port,
                                                       self._pull_mode)
        except (ValueError, IndexError, KeyError):
            return None

        def read_gpio():
            """Read state from GPIO."""
            self._state = remote_rpi_gpio.read_input(self._button)
            self.schedule_update_ha_state()

#        self._state = remote_rpi_gpio.read_input(self._button)

        self._button.when_released = read_gpio
        self._button.when_pressed = read_gpio

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

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        return None

    def update(self):
        """Update the GPIO state."""
        try:
            self._state = remote_rpi_gpio.read_input(self._button)
        except requests.exceptions.ConnectionError:
            return
