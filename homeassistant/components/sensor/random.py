"""
Support for showing random numbers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.random/
"""
import asyncio
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_NAME, CONF_MINIMUM, CONF_MAXIMUM)
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Random Sensor'
DEFAULT_MIN = 0
DEFAULT_MAX = 20

ICON = 'mdi:hanger'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_MAXIMUM, default=DEFAULT_MAX): cv.positive_int,
    vol.Optional(CONF_MINIMUM, default=DEFAULT_MIN): cv.positive_int,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup the Random number sensor."""
    name = config.get(CONF_NAME)
    minimum = config.get(CONF_MINIMUM)
    maximum = config.get(CONF_MAXIMUM)

    async_add_devices([RandomSensor(name, minimum, maximum)], True)
    return True


class RandomSensor(Entity):
    """Representation of a Random number sensor."""

    def __init__(self, name, minimum, maximum):
        """Initialize the sensor."""
        self._name = name
        self._minimum = minimum
        self._maximum = maximum
        self._state = None

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    @asyncio.coroutine
    def async_update(self):
        """Get a new number and updates the states."""
        from random import randrange
        self._state = randrange(self._minimum, self._maximum + 1)
