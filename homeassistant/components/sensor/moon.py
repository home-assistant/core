"""
Support for tracking the moon phases.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.moon/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_NAME)
import homeassistant.util.dt as dt_util
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['astral==1.3.3']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Moon'

ICON = 'mdi:brightness-3'

MOON_PHASES = {
    0: 'New moon',
    7: 'First quarter',
    14: 'Full moon',
    21: 'Last quarter',
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Moon sensor."""
    name = config.get(CONF_NAME)

    yield from async_add_devices([MoonSensor(name)], True)
    return True


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
        if self._state >= 21:
            return 'Last quarter'
        elif self._state >= 14:
            return 'Full moon'
        elif self._state >= 7:
            return 'First quarter'
        else:
            return 'New moon'

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return 'Phase'

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    @asyncio.coroutine
    def async_update(self):
        """Get the time and updates the states."""
        from astral import Astral

        today = dt_util.as_local(dt_util.utcnow()).date()
        self._state = Astral().moon_phase(today)
