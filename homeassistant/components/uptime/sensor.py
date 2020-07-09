"""Platform to retrieve uptime for Home Assistant."""
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, CONF_UNIT_OF_MEASUREMENT
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Uptime"

ICON = "mdi:clock"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT, default="days"): vol.All(
            cv.string, vol.In(["minutes", "hours", "days", "seconds"])
        ),
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the uptime sensor platform."""
    name = config.get(CONF_NAME)
    units = config.get(CONF_UNIT_OF_MEASUREMENT)

    async_add_entities([UptimeSensor(name, units)], True)


class UptimeSensor(Entity):
    """Representation of an uptime sensor."""

    def __init__(self, name, unit):
        """Initialize the uptime sensor."""
        self._name = name
        self._unit = unit
        self.initial = dt_util.now()
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to display in the front end."""
        return ICON

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement the value is expressed in."""
        return self._unit

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    async def async_update(self):
        """Update the state of the sensor."""
        delta = dt_util.now() - self.initial
        div_factor = 3600

        if self.unit_of_measurement == "days":
            div_factor *= 24
        elif self.unit_of_measurement == "minutes":
            div_factor /= 60
        elif self.unit_of_measurement == "seconds":
            div_factor /= 3600

        delta = delta.total_seconds() / div_factor
        self._state = round(delta, 2)
        _LOGGER.debug("New value: %s", delta)
