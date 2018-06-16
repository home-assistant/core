"""
Platform to retrieve uptime for Home Assistant.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.uptime/
"""
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Uptime'

ICON = 'mdi:timer'

DEVICE_CLASS = 'datetime'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


async def async_setup_platform(
        hass, config, async_add_devices, discovery_info=None):
    """Set up the uptime sensor platform."""
    name = config.get(CONF_NAME)

    async_add_devices([UptimeSensor(name)], True)


class UptimeSensor(Entity):
    """Representation of an uptime sensor."""

    def __init__(self, name):
        """Initialize the uptime sensor."""
        self._name = name
        self._state = dt_util.now()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to display in the front end."""
        return ICON

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return DEVICE_CLASS

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state
