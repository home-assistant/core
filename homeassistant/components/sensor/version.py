"""
Support for displaying the current version of Home Assistant.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.version/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import __version__, CONF_NAME
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Current Version"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


async def async_setup_platform(
        hass, config, async_add_devices, discovery_info=None):
    """Set up the Version sensor platform."""
    name = config.get(CONF_NAME)

    async_add_devices([VersionSensor(name)])


class VersionSensor(Entity):
    """Representation of a Home Assistant version sensor."""

    def __init__(self, name):
        """Initialize the Version sensor."""
        self._name = name
        self._state = __version__

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state
