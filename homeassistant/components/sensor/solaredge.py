"""
Support for SolarEdge Monitoring API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.solaredge/
"""

from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.light import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_API_KEY, CONF_MONITORED_VARIABLES, CONF_NAME)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['solaredge==0.0.2']

DOMAIN = "solaredge"

# Config for solaredge monitoring api requests.
CONF_SITE_ID = "site_id"

UPDATE_DELAY = timedelta(minutes=10)
SCAN_INTERVAL = timedelta(minutes=10)

# Supported sensor types:
# Key: ['json_key', 'name', unit, icon]
SENSOR_TYPES = {
    'life_time_data': ['lifeTimeData', "Lifetime energy", 'Wh',
                       'mdi:solar-power'],
    'last_year_data': ['lastYearData', "Energy this year", 'Wh',
                       'mdi:solar-power'],
    'last_month_data': ['lastMonthData', "Energy this month", 'Wh',
                        'mdi:solar-power'],
    'last_day_data': ['lastDayData', "Energy today", 'Wh',
                      'mdi:solar-power'],
    'current_power': ['currentPower', "Current Power", 'W',
                      'mdi:solar-power']
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_SITE_ID): cv.string,
    vol.Optional(CONF_NAME, default='SolarEdge'): cv.string,
    vol.Optional(CONF_MONITORED_VARIABLES, default=['current_power']):
    vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)])
})

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Create the SolarEdge Monitoring API sensor."""
    import solaredge
    from requests.exceptions import HTTPError, ConnectTimeout

    api_key = config[CONF_API_KEY]
    site_id = config[CONF_SITE_ID]
    platform_name = config[CONF_NAME]

    _LOGGER.debug("Setting up SolarEdge Monitoring API")

    # Create new SolarEdge object to retrieve data
    api = solaredge.Solaredge(api_key)

    # Check if api can be reached and site is active
    try:
        response = api.get_details(site_id)

        if response['details']['status'].lower() != 'active':
            _LOGGER.debug("SolarEdge site is not active")
            return False
        _LOGGER.debug("Credentials correct and site is active")
    except KeyError:
        _LOGGER.debug("Missing details data in solaredge response")
        return False
    except (ConnectTimeout, HTTPError):
        _LOGGER.debug("Could not retrieve details from SolarEdge \
         Monitoring API")
        return False

    # Create solaredge data service which will retrieve and update the data.
    data = SolarEdgeData(hass, api, site_id)

    # Create a new sensor for each sensor type.
    entities = []
    for sensor_key in config[CONF_MONITORED_VARIABLES]:
        sensor = SolarEdgeSensor(platform_name, sensor_key, data)
        entities.append(sensor)

    add_entities(entities, True)


class SolarEdgeSensor(Entity):
    """Representation of an SolarEdge Monitoring API sensor."""

    def __init__(self, platform_name, sensor_key, data):
        """Initialize the sensor."""
        self.platform_name = platform_name
        self.sensor_key = sensor_key
        self.data = data
        self._state = None

        self._json_key = SENSOR_TYPES[self.sensor_key][0]
        self._name = SENSOR_TYPES[self.sensor_key][1]
        self._unit_of_measurement = SENSOR_TYPES[self.sensor_key][2]

    @property
    def name(self):
        """Return the name."""
        return "{}_{}".format(self.platform_name, self.sensor_key)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return the sensor icon."""
        return SENSOR_TYPES[self.sensor_key][3]

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    async def async_update(self):
        """Get the latest data from the sensor and update the state."""
        _LOGGER.debug("async_update")
        await self.hass.async_add_job(self.data.update)
        self._state = self.data.data[self._json_key]


class SolarEdgeData:
    """Get and update the latest data."""

    def __init__(self, hass, api, site_id):
        """Initialize the data object."""
        self.hass = hass
        self.api = api
        self.data = {}
        self.site_id = site_id

        self.update()

    @Throttle(UPDATE_DELAY)
    def update(self):
        """Update the data from the SolarEdge Monitoring API."""
        from requests.exceptions import HTTPError, ConnectTimeout

        try:
            data = self.api.get_overview(self.site_id)
            overview = data['overview']
        except KeyError:
            _LOGGER.debug("Missing overview data, skipping update")
            return
        except (ConnectTimeout, HTTPError):
            _LOGGER.debug("Could not retrieve data, skipping update")
            return

        self.data = {}

        for item in overview:
            value = overview[item]
            if 'energy' in value:
                self.data[item] = value['energy']
            elif 'power' in value:
                self.data[item] = value['power']

        _LOGGER.debug("Updated SolarEdge overview data: %s", self.data)
        return
