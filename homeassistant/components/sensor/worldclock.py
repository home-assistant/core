"""
Support for showing the time in a different time zone.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.worldclock/
"""
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_NAME, CONF_TIME_ZONE)
import homeassistant.util.dt as dt_util
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Worldclock Sensor'
ICON = 'mdi:clock'
TIME_STR_FORMAT = "%H:%M"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_TIME_ZONE): cv.time_zone,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Worldclock sensor."""
    name = config.get(CONF_NAME)
    time_zone = dt_util.get_time_zone(config.get(CONF_TIME_ZONE))

    add_devices([WorldClockSensor(time_zone, name)])


class WorldClockSensor(Entity):
    """Representation of a Worldclock sensor."""

    def __init__(self, time_zone, name):
        """Initialize the sensor."""
        self._name = name
        self._time_zone = time_zone
        self._state = None
        self.update()

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

    def update(self):
        """Get the time and updates the states."""
        self._state = dt_util.now(time_zone=self._time_zone).strftime(
            TIME_STR_FORMAT)
