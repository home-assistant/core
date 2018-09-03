"""
Platform to retrieve Jewish calendar information for Home Assistant.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.jewish_calendar/
"""
import logging
from datetime import datetime as dt

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['hdate==0.6.1']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Jewish Calendar'

ICON = 'mdi:clock'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the Jewish calendar sensor platform."""
    name = config.get(CONF_NAME)

    async_add_entities([JewishCalSensor(name)], True)


class JewishCalSensor(Entity):
    """Representation of an Jewish calendar sensor."""

    def __init__(self, name):
        """Initialize the Jewish calendar sensor."""
        self._name = name
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
    def state(self):
        """Return the state of the sensor."""
        return self._state

    async def async_update(self):
        """Update the state of the sensor."""
        import hdate

        self._state = str(hdate.HDate(dt.today(), hebrew=False))
        _LOGGER.debug("New value: %s", self._state)
