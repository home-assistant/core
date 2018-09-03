"""
Platform to retrieve Jewish calendar information for Home Assistant.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.jewish_calendar/
"""
import logging
from datetime import datetime as dt

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['hdate==0.6.1']

_LOGGER = logging.getLogger(__name__)

CONF_LANGUAGE = 'english'

DEFAULT_NAME = 'Jewish Calendar'

ICON = 'mdi:clock'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_LANGUAGE, default='english'): cv.string
})


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the Jewish calendar sensor platform."""
    language = config.get(CONF_LANGUAGE)

    async_add_entities([JewishCalSensor(language)])


class JewishCalSensor(Entity):
    """Representation of an Jewish calendar sensor."""

    def __init__(self, language):
        """Initialize the Jewish calendar sensor."""
        self._date = dt.today()
        self._hebrew = (language == 'hebrew')
        self._state = None
        _LOGGER.debug("Sensor initialized with date %s", self._date)

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

        self._state = str(hdate.HDate(self._date, hebrew=self._hebrew))
        _LOGGER.debug("New value: %s", self._state)
