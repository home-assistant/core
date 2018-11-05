"""
A sensor platform that give you information about next departures from Ruter.

For more details about this platform, please refer to the documentation at
https://www.home-assistant.io/components/sensor.tautulli/
"""
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['pyruter==1.0.2']

_LOGGER = logging.getLogger(__name__)

CONF_STOPID = 'stopid'
CONF_DESTINATION = 'destination'
CONF_OFFSETT = 'offsett'

DEFAULT_NAME = 'Ruter'

TIME_BETWEEN_UPDATES = timedelta(seconds=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_STOPID): cv.positive_int,
    vol.Optional(CONF_DESTINATION): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_OFFSETT, default=1): cv.positive_int,
    })


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Create the sensor."""
    from pyruter.api import Departures

    stopid = config[CONF_STOPID]
    destination = config.get(CONF_DESTINATION)
    name = config[CONF_NAME]
    offsett = config[CONF_OFFSETT]

    ruter = Departures(hass.loop, stopid, destination)
    sensor = [TautulliSensor(ruter, name, offsett)]
    async_add_entities(sensor, True)


class TautulliSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, ruter, name, offsett):
        """Initialize the sensor."""
        self.ruter = ruter
        self._attributes = {}
        self._name = name
        self._offset = offsett
        self._line = None
        self._destination = None
        self._state = None

    async def async_update(self):
        """Get the latest data from the Ruter API."""
        await self.ruter.get_departures()
        if self.ruter.departures is not None:
            try:
                data = self.ruter.departures[self._offset]
                self._state = data['time']
                self._line = data['line']
                self._destination = data['destination']
            except (KeyError, IndexError) as error:
                _LOGGER.error("Error getting data from Ruter, %s", error)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return 'mdi:bus'

    @property
    def device_state_attributes(self):
        """Return attributes for the sensor."""
        return self._attributes
