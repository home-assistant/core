"""
Support for SolarEdge Monitoring API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.solaredge/
"""

import asyncio
from datetime import timedelta
import logging

import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.const import CONF_MONITORED_VARIABLES
from homeassistant.components.light import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util

REQUIREMENTS = ['solaredge==0.0.2']

DOMAIN = "solaredge"

# Config for solaredge monitoring api requests.
CONF_API_KEY = "api_key"
CONF_SITE_ID = "site_id"

DELAY_OK = 10
DELAY_NOT_OK = 20

# Supported sensor types:
# Key: ['name', unit, icon]
SENSOR_TYPES = {
    'lifeTimeData': ["Lifetime energy", 'Wh', 'mdi:solar-power'],
    'lastYearData': ["Energy this year", 'Wh', 'mdi:solar-power'],
    'lastMonthData': ["Energy this month", 'Wh', 'mdi:solar-power'],
    'lastDayData': ["Energy today", 'Wh', 'mdi:solar-power'],
    'currentPower': ["Current Power", 'W', 'mdi:solar-power']
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_SITE_ID): cv.string,
    vol.Optional(CONF_MONITORED_VARIABLES, default=[]):
    vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)])
})

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_entities,
                         discovery_info=None):
    """Create the SolarEdge Monitoring API sensor."""
    api_key = config.get(CONF_API_KEY, None)
    site_id = config.get(CONF_SITE_ID, None)

    # Create solaredge data service which will retrieve and update the data.
    data = SolarEdgeData(hass, api_key, site_id)

    # Create a new sensor for each sensor type.
    entities = []
    for sensor_type in config[CONF_MONITORED_VARIABLES]:
        sensor = SolarEdgeSensor(sensor_type, data)
        entities.append(sensor)

    async_add_entities(entities, True)

    # Schedule first data service update straight away.
    async_track_point_in_utc_time(hass, data.async_update, dt_util.utcnow())


class SolarEdgeSensor(Entity):
    """Representation of an SolarEdge Monitoring API sensor."""

    def __init__(self, sensorType, data):
        """Initialize the sensor."""
        self.type = sensorType
        self.data = data

        self._name = SENSOR_TYPES[self.type][0]
        self._unit_of_measurement = SENSOR_TYPES[self.type][1]

    @property
    def name(self):
        """Return the name."""
        return 'solaredge_' + self.type

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return the sensor icon."""
        return SENSOR_TYPES[self.type][2]

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.type in self.data.data:
            return self.data.data.get(self.type)
        return 0


class SolarEdgeData:
    """Get and update the latest data."""

    def __init__(self, hass, api_key, site_id):
        """Initialize the data object."""
        self.hass = hass
        self.data = {}
        self.api_key = api_key
        self.site_id = site_id

    @asyncio.coroutine
    def schedule_update(self, minutes):
        """Schedule an update after minute minutes."""
        nxt = dt_util.utcnow() + timedelta(minutes=minutes)
        _LOGGER.debug("Scheduling next SolarEdge update in %s minutes",
                      minutes)
        async_track_point_in_utc_time(self.hass, self.async_update, nxt)

    @asyncio.coroutine
    def async_update(self, *_):
        """Update the data from the SolarEdge Monitoring API."""
        import solaredge
        from requests.exceptions import HTTPError, ConnectTimeout

        # Create new SolarEdge object to retrieve data
        api = solaredge.Solaredge(self.api_key)

        try:
            data = api.get_overview(self.site_id)
        except (ConnectTimeout, HTTPError):
            _LOGGER.debug("Could not retrieve data, delaying next update")
            yield from self.schedule_update(DELAY_NOT_OK)
            return

        if 'overview' not in data:
            _LOGGER.debug("Missing overview data, delaying next update")
            yield from self.schedule_update(DELAY_NOT_OK)
            return

        overview = data['overview']

        self.data = {}

        for item in overview:
            value = overview[item]
            if 'energy' in value:
                self.data[item] = value['energy']
            elif 'power' in value:
                self.data[item] = value['power']

        _LOGGER.debug("Updated SolarEdge overview data: %s", self.data)

        yield from self.schedule_update(DELAY_OK)
        return
