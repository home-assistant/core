"""Support for showing the time in a different time zone."""
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, CONF_TIME_ZONE
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
import homeassistant.util.dt as dt_util

CONF_TIME_FORMAT = "time_format"

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Worldclock Sensor"
ICON = "mdi:clock"
DEFAULT_TIME_STR_FORMAT = "%H:%M"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_TIME_ZONE): cv.time_zone,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_TIME_FORMAT, default=DEFAULT_TIME_STR_FORMAT): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the World clock sensor."""
    name = config.get(CONF_NAME)
    time_zone = dt_util.get_time_zone(config.get(CONF_TIME_ZONE))

    async_add_entities(
        [
            WorldClockSensor(
                time_zone,
                name,
                config.get(CONF_TIME_FORMAT),
            )
        ],
        True,
    )


class WorldClockSensor(Entity):
    """Representation of a World clock sensor."""

    def __init__(self, time_zone, name, time_format):
        """Initialize the sensor."""
        self._name = name
        self._time_zone = time_zone
        self._state = None
        self._time_format = time_format

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

    async def async_update(self):
        """Get the time and updates the states."""
        self._state = dt_util.now(time_zone=self._time_zone).strftime(self._time_format)
