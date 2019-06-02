"""Support for De Lijn (Flemish public transport) information."""
import asyncio
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.exceptions import PlatformNotReady

_LOGGER = logging.getLogger(__name__)

CONF_NEXT_PASSAGE = 'nextpassage'
CONF_STOP_ID = 'stop_id'
CONF_SUB_KEY = 'sub_key'
CONF_MAX_PASSAGES = 'max_passages'

DEFAULT_NAME = 'De Lijn'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SUB_KEY): cv.string,
    vol.Required(CONF_NEXT_PASSAGE): [{
        vol.Required(CONF_STOP_ID): cv.string,
        vol.Optional(CONF_MAX_PASSAGES, default=5): cv.positive_int}]
})


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Create the sensor."""
    from pydelijn.api import Passages

    sub_key = config.get(CONF_SUB_KEY)
    name = DEFAULT_NAME

    session = async_get_clientsession(hass)

    sensors = []
    for nextpassage in config.get(CONF_NEXT_PASSAGE):
        stop_id = nextpassage[CONF_STOP_ID]
        max_passages = nextpassage[CONF_MAX_PASSAGES]
        line = Passages(hass.loop, stop_id, max_passages, sub_key, session)
        sensors.append(DeLijnPublicTransportSensor(line, name))

    tasks = [sensor.async_update() for sensor in sensors]
    if tasks:
        await asyncio.wait(tasks)
    if not all(sensor._attributes for sensor in sensors):
        raise PlatformNotReady

    async_add_entities(sensors, True)


class DeLijnPublicTransportSensor(Entity):
    """Representation of a Ruter sensor."""

    def __init__(self, line, name):
        """Initialize the sensor."""
        self.line = line
        self._attributes = {}
        self._name = name
        self._state = None

    async def async_update(self):
        """Get the latest data from the De Lijn API."""
        await self.line.get_passages()
        if self.line.passages is None:
            _LOGGER.error("No data recieved from De Lijn.")
            return
        try:
            attributes = {}
            first = self.line.passages[0]
            self._state = first['due_in_min']
            self._name = first['stopname']
            attributes['stopname'] = first['stopname']
            attributes['line_number_public'] = first['line_number_public']
            attributes['line_transport_type'] = first['line_transport_type']
            attributes['final_destination'] = first['final_destination']
            attributes['due_at_sch'] = first['due_at_sch']
            attributes['due_at_rt'] = first['due_at_rt']
            attributes['due_in_min'] = first['due_in_min']
            attributes['next_passages'] = self.line.passages
            self._attributes = attributes
        except (KeyError, IndexError) as error:
            _LOGGER.debug("Error getting data from De Lijn, %s", error)

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
