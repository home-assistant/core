"""
Support for the Environment Canada weather service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.environment_canada/
"""
import datetime
import io
import json
import logging
import os
import re
import csv
import xml.etree.ElementTree as et

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS, TEMP_CELSIUS, CONF_NAME, CONF_LATITUDE,
    CONF_LONGITUDE, ATTR_ATTRIBUTION, ATTR_HIDDEN)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from homeassistant.util.location import distance
import homeassistant.util.dt as dt
import homeassistant.helpers.config_validation as cv

_BASE_URL = 'http://dd.weatheroffice.ec.gc.ca/citypage_weather/xml/{}_e.xml'
_LOGGER = logging.getLogger(__name__)

ATTR_UPDATED = 'updated'
ATTR_SENSOR_TYPE = 'sensor_type'
ATTR_STATION = 'station'
ATTR_LOCATION = 'location'

CONF_ATTRIBUTION = "Data provided by Environment Canada"
CONF_STATION = 'station'

MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(minutes=10)
MAX_CACHE_AGE = datetime.timedelta(days=30)

SENSOR_TYPES = {
    'temperature': {'name': 'Temperature',
                    'type': 'value',
                    'xpath': './currentConditions/temperature',
                    'unit': TEMP_CELSIUS},
    'dewpoint': {'name': 'Dew Point',
                 'type': 'value',
                 'xpath': './currentConditions/dewpoint',
                 'unit': TEMP_CELSIUS},
    'wind_chill': {'name': 'Wind Chill',
                   'type': 'value',
                   'xpath': './currentConditions/windChill',
                   'unit': TEMP_CELSIUS},
    'humidex': {'name': 'Humidex',
                'type': 'value',
                'xpath': './currentConditions/humidex',
                'unit': TEMP_CELSIUS},
    'pressure': {'name': 'Pressure',
                 'type': 'value',
                 'xpath': './currentConditions/pressure',
                 'unit': 'kPa'},
    'tendency': {'name': 'Tendency',
                 'type': 'attribute',
                 'xpath': './currentConditions/pressure',
                 'attribute': 'tendency'},
    'humidity': {'name': 'Humidity',
                 'type': 'value',
                 'xpath': './currentConditions/relativeHumidity',
                 'unit': '%'},
    'visibility': {'name': 'Visibility',
                   'type': 'value',
                   'xpath': './currentConditions/visibility',
                   'unit': 'km'},
    'condition': {'name': 'Condition',
                  'type': 'value',
                  'xpath': './currentConditions/condition'},
    'wind_speed': {'name': 'Wind Speed',
                   'type': 'value',
                   'xpath': './currentConditions/wind/speed',
                   'unit': 'km/h'},
    'wind_gust': {'name': 'Wind Gust',
                  'type': 'value',
                  'xpath': './currentConditions/wind/gust',
                  'unit': 'km/h'},
    'wind_dir': {'name': 'Wind Direction',
                 'type': 'value',
                 'xpath': './currentConditions/wind/direction'},
    'high_temp': {'name': 'High Temperature',
                  'type': 'value',
                  'xpath': './forecastGroup/forecast/'
                           'temperatures/temperature[@class="high"]',
                  'unit': TEMP_CELSIUS},
    'low_temp': {'name': 'Low Temperature',
                 'type': 'value',
                 'xpath': './forecastGroup/forecast/'
                          'temperatures/temperature[@class="low"]',
                 'unit': TEMP_CELSIUS},
    'pop': {'name': 'Chance of Precip.',
            'type': 'value',
            'xpath': './forecastGroup/forecast/abbreviatedForecast/pop',
            'unit': '%'},
    'warning': {'name': 'Warning',
                'type': 'attribute',
                'xpath': './warnings/event',
                'attribute': 'description'}
}


def validate_station(station):
    """Check that the station ID is well-formed."""
    if station is None:
        return
    if not re.fullmatch(r'[A-Z]{2}/s0000\d{3}', station):
        raise vol.error.Invalid('Station ID must be of the form "XX/s0000###"')
    return station


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MONITORED_CONDITIONS, default=list(SENSOR_TYPES.keys())):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_STATION): validate_station,
    vol.Inclusive(CONF_LATITUDE, 'latlon'): cv.latitude,
    vol.Inclusive(CONF_LONGITUDE, 'latlon'): cv.longitude,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Environment Canada sensor."""
    station = get_station(hass, config)
    ec_data = ECData(hass, station)

    try:
        ec_data.update()
    except ValueError as err:
        _LOGGER.error("Received error from EC Current: %s", err)
        return

    add_devices([ECSensor(ec_data, sensor_type, config.get(CONF_NAME))
                 for sensor_type in config.get(CONF_MONITORED_CONDITIONS,
                                               list(SENSOR_TYPES.keys()))])


class ECSensor(Entity):
    """Implementation of an Environment Canada sensor."""

    def __init__(self, ec_data, sensor_type, stationname):
        """Initialize the sensor."""
        self.data_object = ec_data
        self.data_element = ec_data.data
        self._sensor_type = sensor_type
        self.stationname = stationname

    @property
    def name(self):
        """Return the name of the sensor."""
        if self.stationname is None:
            return 'EC {}'.format(SENSOR_TYPES[self._sensor_type]['name'])

        return 'EC {} {}'.format(
            self.stationname, SENSOR_TYPES[self._sensor_type]['name'])

    @property
    def state(self):
        """Return the state of the sensor."""
        sensor = SENSOR_TYPES[self._sensor_type]

        if sensor['type'] == 'value':
            value = self.data_element.findtext(sensor['xpath'])
            if value:
                return value
            return None

        elif sensor['type'] == 'attribute':
            element = self.data_element.find(sensor['xpath'])
            if element:
                value = element.attrib.get(sensor['attribute'])
                if value:
                    return value
            return None

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        timestamp = self.data_element.findtext(
            './currentConditions/dateTime/timeStamp')
        if timestamp:
            updated_utc = datetime.datetime.strptime(timestamp, '%Y%m%d%H%M%S')
            updated_local = dt.as_local(updated_utc)
        else:
            updated_local = None

        if self.state:
            hidden = False
        else:
            hidden = True

        attr = {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
            ATTR_UPDATED: updated_local,
            ATTR_SENSOR_TYPE: self._sensor_type,
            ATTR_LOCATION: self.data_element.findtext('./location/name'),
            ATTR_STATION: self.data_element.findtext(
                './currentConditions/station'),
            ATTR_HIDDEN: hidden
        }

        return attr

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return SENSOR_TYPES[self._sensor_type].get('unit')

    def update(self):
        """Update current conditions."""
        self.data_object.update()
        self.data_element = self.data_object.data


class ECData(object):
    """Get data from Environment Canada."""

    def __init__(self, hass, station_id):
        """Initialize the data object."""
        self._hass = hass
        self._station_id = station_id
        self._data = None

    def _build_url(self):
        """Build the URL for the requests."""
        url = _BASE_URL.format(self._station_id)
        _LOGGER.debug("URL: %s", url)
        return url

    @property
    def data(self):
        """Return the latest data object."""
        if self._data:
            return self._data
        return None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from Environment Canada."""
        try:
            result = requests.get(self._build_url(), timeout=10)
            site_xml = result.content.decode('iso-8859-1')
            self._data = et.fromstring(site_xml)
        except ValueError as err:
            _LOGGER.error("Check Environment Canada %s", err.args)
            self._data = None
            raise


def get_ec_sites():
    """Get list of all sites from Environment Canada, for auto-config."""
    sites = []

    site_list_url = ('http://dd.weatheroffice.ec.gc.ca/'
                     'citypage_weather/docs/site_list_en.csv')

    sites_csv_string = requests.get(url=site_list_url, timeout=10).text
    sites_csv_stream = io.StringIO(sites_csv_string)

    sites_csv_stream.seek(0)
    next(sites_csv_stream)

    sites_reader = csv.DictReader(sites_csv_stream)

    for site in sites_reader:
        if site['Province Codes'] != 'HEF':
            site['Latitude'] = float(site['Latitude'].replace('N', ''))
            site['Longitude'] = -1 * float(site['Longitude'].replace('W', ''))
            sites.append(site)

    return sites


def cache_expired(file):
    """Return whether cache should be refreshed."""
    cache_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(file))
    return datetime.datetime.utcnow() - cache_mtime > MAX_CACHE_AGE


def ec_sites(cache_dir):
    """Return list of all sites, for auto-config.

    Results from internet requests are cached, making
    subsequent calls faster.
    """
    cache_file = os.path.join(cache_dir, '.ec-sites.json')

    if not os.path.isfile(cache_file) or cache_expired(cache_file):
        sites = get_ec_sites()

        with open(cache_file, 'w') as cache:
            cache.write(json.dumps(sites))
        return sites
    else:
        with open(cache_file, 'r') as cache:
            return json.loads(cache.read())


def closest_site(lat, lon, cache_dir):
    """Return the province/site_code of the closest station to our lat/lon."""
    if lat is None or lon is None or not os.path.isdir(cache_dir):
        return

    sites = ec_sites(cache_dir)

    def site_distance(site):
        """Calculate distance to a site."""
        return distance(lat, lon, site['Latitude'], site['Longitude'])

    closest = min(sites, key=site_distance)

    return '{}/{}'.format(closest['Province Codes'], closest['Codes'])


def get_station(hass, config):
    """Determine station to use.

    Preference is for user-provided station ID, followed by closest station to
    platform-specific coordinates, then closest station to
    top-level coordinates.
    """
    if config.get(CONF_STATION):
        station = config[CONF_STATION]
    elif config.get(CONF_LATITUDE) and config.get(CONF_LONGITUDE):
        station = closest_site(
            config[CONF_LATITUDE],
            config[CONF_LONGITUDE],
            hass.config.config_dir)
    else:
        station = closest_site(
            hass.config.latitude,
            hass.config.longitude,
            hass.config.config_dir)

    if station is None:
        _LOGGER.error("Could not get weather station")
        return None
    return station
