"""
Support for showing random states.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.random/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA, DEVICE_CLASSES_SCHEMA)
from homeassistant.const import CONF_NAME, CONF_DEVICE_CLASS

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Random Binary Sensor'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
})


async def async_setup_platform(
        hass, config, async_add_devices, discovery_info=None):
    """Set up the Random binary sensor."""
    name = config.get(CONF_NAME)
    device_class = config.get(CONF_DEVICE_CLASS)

    async_add_devices([RandomSensor(name, device_class)], True)


class RandomSensor(BinarySensorDevice):
    """Representation of a Random binary sensor."""

    def __init__(self, name, device_class):
        """Initialize the Random binary sensor."""
        self._name = name
        self._device_class = device_class
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._state

    @property
    def device_class(self):
        """Return the sensor class of the sensor."""
        return self._device_class

    async def async_update(self):
        """Get new state and update the sensor's state."""
        from random import getrandbits
        self._state = bool(getrandbits(1))
