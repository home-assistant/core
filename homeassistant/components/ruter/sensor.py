"""A sensor to provide information about next departures from Ruter."""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

CONF_STOP_ID = 'stop_id'
CONF_DESTINATION = 'destination'
CONF_OFFSET = 'offset'

DEFAULT_NAME = 'Ruter'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_STOP_ID): cv.positive_int,
    vol.Optional(CONF_DESTINATION): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_OFFSET, default=0): cv.positive_int,
    })


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Create the sensor."""
    from pyruter.api import Departures
    _LOGGER.warning("The API used in this sensor is shutting down soon, "
                    "you should consider starting to use the "
                    "'entur_public_transport' sensor instead")
    stop_id = config[CONF_STOP_ID]
    destination = config.get(CONF_DESTINATION)
    name = config[CONF_NAME]
    offset = config[CONF_OFFSET]

    session = async_get_clientsession(hass)
    ruter = Departures(hass.loop, stop_id, destination, session)
    sensor = [RuterSensor(ruter, name, offset)]
    async_add_entities(sensor, True)


class RuterSensor(Entity):
    """Representation of a Ruter sensor."""

    def __init__(self, ruter, name, offset):
        """Initialize the sensor."""
        self.ruter = ruter
        self._attributes = {}
        self._name = name
        self._offset = offset
        self._state = None

    async def async_update(self):
        """Get the latest data from the Ruter API."""
        await self.ruter.get_departures()
        if self.ruter.departures is None:
            _LOGGER.error("No data recieved from Ruter.")
            return
        try:
            data = self.ruter.departures[self._offset]
            self._state = data['time']
            self._attributes['line'] = data['line']
            self._attributes['destination'] = data['destination']
        except (KeyError, IndexError) as error:
            _LOGGER.debug("Error getting data from Ruter, %s", error)

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
