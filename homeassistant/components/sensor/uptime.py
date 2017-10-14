"""
Component to retrieve uptime for Home Assistant.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.uptime/
"""
import asyncio
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_UNIT_OF_MEASUREMENT)
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Uptime'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_UNIT_OF_MEASUREMENT, default='days'):
        vol.All(cv.string, vol.In(['hours', 'days']))
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the uptime sensor platform."""
    name = config.get(CONF_NAME)
    units = config.get(CONF_UNIT_OF_MEASUREMENT)
    async_add_devices([UptimeSensor(name, units)], True)


class UptimeSensor(Entity):
    """Representation of an uptime sensor."""

    def __init__(self, name, units):
        """Initialize the uptime sensor."""
        self._name = name
        self._icon = 'mdi:clock'
        self._units = units
        self.initial = dt_util.now()
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to display in the front end."""
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement the value is expressed in."""
        return self._units

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @asyncio.coroutine
    def async_update(self):
        """Update the state of the sensor."""
        delta = dt_util.now() - self.initial
        div_factor = 3600
        if self.unit_of_measurement == 'days':
            div_factor *= 24
        delta = delta.total_seconds() / div_factor
        self._state = round(delta, 2)
        _LOGGER.debug("New value: %s", delta)
