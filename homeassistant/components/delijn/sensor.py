"""Support for De Lijn (Flemish public transport) information."""
import logging

from pydelijn.api import Passages
import pytz
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, DEVICE_CLASS_TIMESTAMP)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data provided by data.delijn.be"

CONF_NEXT_DEPARTURE = 'next_departure'
CONF_STOP_ID = 'stop_id'
CONF_API_KEY = 'api_key'
CONF_NUMBER_OF_DEPARTURES = 'number_of_departures'

DEFAULT_NAME = 'De Lijn'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_NEXT_DEPARTURE): [{
        vol.Required(CONF_STOP_ID): cv.string,
        vol.Optional(CONF_NUMBER_OF_DEPARTURES, default=5): cv.positive_int}]
})


def due_in_minutes(timestamp):
    """Get the time in minutes from a timestamp."""
    if timestamp is None:
        return None
    diff = timestamp - dt_util.now()
    return int(diff.total_seconds() / 60)


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Create the sensor."""
    api_key = config[CONF_API_KEY]
    name = DEFAULT_NAME

    session = async_get_clientsession(hass)

    sensors = []
    for nextpassage in config[CONF_NEXT_DEPARTURE]:
        stop_id = nextpassage[CONF_STOP_ID]
        number_of_departures = nextpassage[CONF_NUMBER_OF_DEPARTURES]
        line = Passages(hass.loop,
                        stop_id,
                        number_of_departures,
                        api_key,
                        session)
        await line.get_passages()
        if line.passages is None:
            _LOGGER.error("No data recieved from De Lijn")
            return
        sensors.append(DeLijnPublicTransportSensor(line, name))

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
            _LOGGER.error("No data recieved from De Lijn")
            return
        try:
            attributes = {}
            first = self.line.passages[0]
            local_timezone = pytz.timezone("Europe/Brussels")
            if first['due_at_rt'] is not None:
                first_passage_naive = dt_util.parse_datetime(
                    first['due_at_rt'])
            else:
                first_passage_naive = dt_util.parse_datetime(
                    first['due_at_sch'])
            first_passage_local = local_timezone.localize(first_passage_naive)
            first_passage_utc = dt_util.as_utc(first_passage_local)
            self._state = first_passage_utc.isoformat()
            self._name = first['stopname']
            attributes['stopname'] = first['stopname']
            attributes['line_number_public'] = first['line_number_public']
            attributes['line_transport_type'] = first['line_transport_type']
            attributes['final_destination'] = first['final_destination']
            attributes['due_at_schedule'] = first['due_at_sch']
            attributes['due_at_realtime'] = first['due_at_rt']
            attributes['due_in_min'] = first['due_in_min']
            attributes['next_passages'] = self.line.passages
            self._attributes = attributes
        except (KeyError, IndexError) as error:
            _LOGGER.debug("Error getting data from De Lijn, {}".format(error))

    @property
    def device_class(self):
        """Return the device class."""
        return DEVICE_CLASS_TIMESTAMP

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
        self._attributes[ATTR_ATTRIBUTION] = ATTRIBUTION
        return self._attributes
