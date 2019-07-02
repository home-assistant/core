"""
Support for the Environment Canada weather service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.environment_canada/
"""
import datetime
import logging
import re

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS, TEMP_CELSIUS, CONF_NAME, CONF_LATITUDE,
    CONF_LONGITUDE, ATTR_ATTRIBUTION, ATTR_LOCATION, ATTR_HIDDEN)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.util.dt as dt
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

ATTR_UPDATED = 'updated'
ATTR_STATION = 'station'
ATTR_DETAIL = 'alert detail'
ATTR_TIME = 'alert time'

CONF_ATTRIBUTION = "Data provided by Environment Canada"
CONF_STATION = 'station'

MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(minutes=10)

SENSOR_TYPES = {
    'temperature': {'name': 'Temperature',
                    'unit': TEMP_CELSIUS},
    'dewpoint': {'name': 'Dew Point',
                 'unit': TEMP_CELSIUS},
    'wind_chill': {'name': 'Wind Chill',
                   'unit': TEMP_CELSIUS},
    'humidex': {'name': 'Humidex',
                'unit': TEMP_CELSIUS},
    'pressure': {'name': 'Pressure',
                 'unit': 'kPa'},
    'tendency': {'name': 'Tendency'},
    'humidity': {'name': 'Humidity',
                 'unit': '%'},
    'visibility': {'name': 'Visibility',
                   'unit': 'km'},
    'condition': {'name': 'Condition'},
    'wind_speed': {'name': 'Wind Speed',
                   'unit': 'km/h'},
    'wind_gust': {'name': 'Wind Gust',
                  'unit': 'km/h'},
    'wind_dir': {'name': 'Wind Direction'},
    'high_temp': {'name': 'High Temperature',
                  'unit': TEMP_CELSIUS},
    'low_temp': {'name': 'Low Temperature',
                 'unit': TEMP_CELSIUS},
    'pop': {'name': 'Chance of Precip.',
            'unit': '%'},
    'warnings': {'name': 'Warnings'},
    'watches': {'name': 'Watches'},
    'advisories': {'name': 'Advisories'},
    'statements': {'name': 'Statements'},
    'endings': {'name': 'Ended'}
}


def validate_station(station):
    """Check that the station ID is well-formed."""
    if station is None:
        return
    if not re.fullmatch(r'[A-Z]{2}/s0000\d{3}', station):
        raise vol.error.Invalid('Station ID must be of the form "XX/s0000###"')
    return station


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MONITORED_CONDITIONS, default=list(SENSOR_TYPES)):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_STATION): validate_station,
    vol.Inclusive(CONF_LATITUDE, 'latlon'): cv.latitude,
    vol.Inclusive(CONF_LONGITUDE, 'latlon'): cv.longitude,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Environment Canada sensor."""
    from env_canada import ECData

    if config.get(CONF_STATION):
        ec_data = ECData(station_id=config[CONF_STATION])
    elif config.get(CONF_LATITUDE) and config.get(CONF_LONGITUDE):
        ec_data = ECData(coordinates=(config[CONF_LATITUDE],
                                      config[CONF_LONGITUDE]))
    else:
        ec_data = ECData(coordinates=(hass.config.latitude,
                                      hass.config.longitude))

    add_devices([ECSensor(sensor_type, ec_data, config.get(CONF_NAME))
                 for sensor_type in config[CONF_MONITORED_CONDITIONS]],
                True)


class ECSensor(Entity):
    """Implementation of an Environment Canada sensor."""

    def __init__(self, sensor_type, ec_data, platform_name):
        """Initialize the sensor."""
        self.sensor_type = sensor_type
        self.ec_data = ec_data
        self.platform_name = platform_name
        self._state = None
        self._attr = None

    @property
    def name(self):
        """Return the name of the sensor."""
        if self.platform_name is None:
            return SENSOR_TYPES[self.sensor_type]['name']

        return ' '.join([self.platform_name,
                         SENSOR_TYPES[self.sensor_type]['name']])

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._attr

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return SENSOR_TYPES[self.sensor_type].get('unit')

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update current conditions."""
        self.ec_data.update()
        self.ec_data.conditions.update(self.ec_data.alerts)

        self._attr = {}

        sensor_data = self.ec_data.conditions.get(self.sensor_type)
        if isinstance(sensor_data, list):
            self._state = ' | '.join([str(s.get('title'))
                                      for s in sensor_data])
            self._attr.update({
                ATTR_DETAIL: ' | '.join([str(s.get('detail'))
                                         for s in sensor_data]),
                ATTR_TIME: ' | '.join([str(s.get('date'))
                                       for s in sensor_data])
            })
        else:
            self._state = sensor_data

        timestamp = self.ec_data.conditions.get('timestamp')
        if timestamp:
            updated_utc = datetime.datetime.strptime(timestamp, '%Y%m%d%H%M%S')
            updated_local = dt.as_local(updated_utc).isoformat()
        else:
            updated_local = None

        hidden = bool(self._state is None or self._state == '')

        self._attr.update({
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
            ATTR_UPDATED: updated_local,
            ATTR_LOCATION: self.ec_data.conditions.get('location'),
            ATTR_STATION: self.ec_data.conditions.get('station'),
            ATTR_HIDDEN: hidden
        })
