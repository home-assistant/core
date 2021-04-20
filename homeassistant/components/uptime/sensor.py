"""Platform to retrieve uptime for Home Assistant."""

import voluptuous as vol

from homeassistant.components.sensor import (
    DEVICE_CLASS_TIMESTAMP,
    PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.const import CONF_NAME, CONF_UNIT_OF_MEASUREMENT
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util

DEFAULT_NAME = "Uptime"

PLATFORM_SCHEMA = vol.All(
    cv.deprecated(CONF_UNIT_OF_MEASUREMENT),
    PLATFORM_SCHEMA.extend(
        {
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_UNIT_OF_MEASUREMENT, default="days"): vol.All(
                cv.string, vol.In(["minutes", "hours", "days", "seconds"])
            ),
        }
    ),
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the uptime sensor platform."""
    name = config.get(CONF_NAME)

    async_add_entities([UptimeSensor(name)], True)


class UptimeSensor(SensorEntity):
    """Representation of an uptime sensor."""

    def __init__(self, name):
        """Initialize the uptime sensor."""
        self._name = name
        self._state = dt_util.now().isoformat()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_class(self):
        """Return device class."""
        return DEVICE_CLASS_TIMESTAMP

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def should_poll(self) -> bool:
        """Disable polling for this entity."""
        return False
