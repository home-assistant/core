"""
Support for SolarEdge Monitoring API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.solaredge/
"""

from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_API_KEY, CONF_MONITORED_CONDITIONS, CONF_NAME)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['solaredge==0.0.2']

# Config for solaredge monitoring api requests.
CONF_SITE_ID = "site_id"

OVERVIEW_UPDATE_DELAY = timedelta(minutes=10)
DETAILS_UPDATE_DELAY = timedelta(hours=12)

SCAN_INTERVAL = timedelta(minutes=10)

# Supported overview sensor types:
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
                      'mdi:solar-power'],
    'site_details': [None, 'Site details', None, None]
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_SITE_ID): cv.string,
    vol.Optional(CONF_NAME, default='SolarEdge'): cv.string,
    vol.Optional(CONF_MONITORED_CONDITIONS, default=['current_power']):
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

    # Create new SolarEdge object to retrieve data
    api = solaredge.Solaredge(api_key)

    # Check if api can be reached and site is active
    try:
        response = api.get_details(site_id)

        if response['details']['status'].lower() != 'active':
            _LOGGER.error("SolarEdge site is not active")
            return
        _LOGGER.debug("Credentials correct and site is active")
    except KeyError:
        _LOGGER.error("Missing details data in solaredge response")
        return
    except (ConnectTimeout, HTTPError):
        _LOGGER.error("Could not retrieve details from SolarEdge API")
        return

    # Create sensor factory that will create sensors based on sensor_key.
    sensor_factory = SolarEdgeSensorFactory(platform_name, site_id, api)

    # Create a new sensor for each sensor type.
    entities = []
    for sensor_key in config[CONF_MONITORED_CONDITIONS]:
        sensor = sensor_factory.create_sensor(sensor_key)
        entities.append(sensor)

    add_entities(entities, True)


class SolarEdgeSensorFactory:
    """Factory which creates sensors based on the sensor_key"""

    def __init__(self, platform_name, site_id, api):
        """Initialize the factory"""
        self.platform_name = platform_name
        
        self.overview_data_service = SolarEdgeOverviewDataService(api, site_id)
        self.details_data_service = SolarEdgeDetailsDataService(api, site_id)

    def create_sensor(self, sensor_key):
        """Create and return a sensor based on the sensor_key"""
        if sensor_key in ['life_time_data', 'last_year_data', 'last_month_data', 'last_day_data', 'current_power']:
            return SolarEdgeOverviewSensor(self.platform_name, sensor_key, 
                    self.overview_data_service)
        elif sensor_key == 'site_details':
            return SolarEdgeDetailsSensor(self.platform_name, sensor_key,
                    self.details_data_service)


class SolarEdgeSensor(Entity):
    """Abstract class for a solaredge sensor"""

    def __init__(self, platform_name, sensor_key, data_service):
        self.platform_name = platform_name
        self.sensor_key = sensor_key
        self.data_service = data_service
        
        self._state = None

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
        return self._icon

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state


class SolarEdgeOverviewSensor(SolarEdgeSensor):
    """Representation of an SolarEdge Monitoring API overview sensor."""

    def __init__(self, platform_name, sensor_key, data_service):
        """Initialize the overview sensor."""
        super().__init__(platform_name, sensor_key, data_service)

        self._json_key = SENSOR_TYPES[self.sensor_key][0]
        self._unit_of_measurement = SENSOR_TYPES[self.sensor_key][2]
        self._icon = SENSOR_TYPES[self.sensor_key][3]

    def update(self):
        """Get the latest data from the sensor and update the state."""
        self.data_service.update()
        self._state = self.data_service.data[self._json_key]


class SolarEdgeDetailsSensor(SolarEdgeSensor):
    """Representation of an SolarEdge Monitoring API details sensor."""

    def __init__(self, platform_name, sensor_key, data_service):
        """Initialize the details sensor."""
        super().__init__(platform_name, sensor_key, data_service)
       
        self._attributes = {}

        self._unit_of_measurement = SENSOR_TYPES[self.sensor_key][2]
        self._icon = SENSOR_TYPES[self.sensor_key][3]

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return self._attributes
    
    def update(self):
        """Get the latest details and update state and attributes"""
        self.data_service.update()
        self._state = self.data_service.data
        self._attributes = self.data_service.attributes


class SolarEdgeDataService:
    """Get and update the latest data."""

    def __init__(self, api, site_id):
        """Initialize the data object."""
        self.api = api
        self.site_id = site_id
        
        self.data = {}
        self.attributes = {}

class SolarEdgeOverviewDataService(SolarEdgeDataService):
    """Get and update the latest overview data."""

    @Throttle(OVERVIEW_UPDATE_DELAY)
    def update(self):
        """Update the data from the SolarEdge Monitoring API."""
        from requests.exceptions import HTTPError, ConnectTimeout

        try:
            data = self.api.get_overview(self.site_id)
            overview = data['overview']
        except KeyError:
            _LOGGER.error("Missing overview data, skipping update")
            return
        except (ConnectTimeout, HTTPError):
            _LOGGER.error("Could not retrieve data, skipping update")
            return

        self.data = {}

        for key, value in overview.items():
            if key in ['lifeTimeData', 'lastYearData', 'lastMonthData', 'lastDayData']:
                data = value['energy']
            elif key in ['currentPower']:
                data = value['power']
            else:
                data = value
            self.data[key] = data

        _LOGGER.debug("Updated SolarEdge overview data: %s", self.data)


class SolarEdgeDetailsDataService(SolarEdgeDataService):
    """Get and update the latest details data."""

    @Throttle(DETAILS_UPDATE_DELAY)
    def update(self):
        """Update the data from the SolarEdge Monitoring API."""
        from requests.exceptions import HTTPError, ConnectTimeout

        try:
            data = self.api.get_details(self.site_id)
            details = data['details']
        except KeyError:
            _LOGGER.error("Missing details data, skipping update")
            return
        except (ConnectTimeout, HTTPError):
            _LOGGER.error("Could not retrieve data, skipping update")
            return

        self.data = {}
        self.attributes = {}

        for key, value in details.items():
            if key in ['primaryModule']:
                self.attributes.update(value)
            elif key in ['peakPower', 'type', 'name', 'lastUpdateTime', 'installationDate']:
                self.attributes[key] = value
            elif key == 'status':
                self.data = value

        _LOGGER.debug("Updated SolarEdge details data and attributes: %s, %s", self.data, self.attributes)

