"""
Support for tracking the moon phases.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.moon/
"""
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_NAME)
import homeassistant.util.dt as dt_util
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Moon'

ICON = 'mdi:brightness-3'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the Moon sensor."""
    name = config.get(CONF_NAME)

    async_add_entities([MoonSensor(name)], True)


class MoonSensor(Entity):
    """Representation of a Moon sensor."""

    def __init__(self, name):
        """Initialize the sensor."""
        self._name = name
        self._state = None

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        if self._state == 0:
            return 'new_moon'
        if self._state < 7:
            return 'waxing_crescent'
        if self._state == 7:
            return 'first_quarter'
        if self._state < 14:
            return 'waxing_gibbous'
        if self._state == 14:
            return 'full_moon'
        if self._state < 21:
            return 'waning_gibbous'
        if self._state == 21:
            return 'last_quarter'
        return 'waning_crescent'

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    async def async_update(self):
        """Get the time and updates the states."""
        from astral import Astral

        today = dt_util.as_local(dt_util.utcnow()).date()
        self._state = Astral().moon_phase(today)
