"""
Sensor for data from Austrian "Zentralanstalt für Meteorologie und Geodynamik".

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.zamg/
"""
import csv
from datetime import datetime, timedelta
import gzip
import json
import logging
import os

from aiohttp.hdrs import USER_AGENT
import pytz
import requests
import voluptuous as vol

from homeassistant.components.weather import (
    ATTR_WEATHER_HUMIDITY, ATTR_WEATHER_PRESSURE, ATTR_WEATHER_WIND_SPEED,
    ATTR_WEATHER_ATTRIBUTION, ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_WIND_BEARING)
from homeassistant.const import (
    CONF_NAME, CONF_LATITUDE, CONF_LONGITUDE, CONF_MONITORED_CONDITIONS,
    __version__)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

ATTR_STATION = 'station'
ATTR_UPDATED = 'updated'
ATTRIBUTION = "Data provided by ZAMG"

CONF_STATION_ID = 'station_id'

DEFAULT_NAME = 'zamg'

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=10)

SENSOR_TYPES = {
    ATTR_WEATHER_PRESSURE: ('Pressure', 'hPa', 'LDstat hPa', float),
    'pressure_sealevel': ('Pressure at Sea Level', 'hPa', 'LDred hPa', float),
    ATTR_WEATHER_HUMIDITY: ('Humidity', '%', 'RF %', int),
    ATTR_WEATHER_WIND_SPEED: ('Wind Speed', 'km/h', 'WG km/h', float),
    ATTR_WEATHER_WIND_BEARING: ('Wind Bearing', '°', 'WR °', int),
    'wind_max_speed': ('Top Wind Speed', 'km/h', 'WSG km/h', float),
    'wind_max_bearing': ('Top Wind Bearing', '°', 'WSR °', int),
    'sun_last_hour': ('Sun Last Hour', '%', 'SO %', int),
    ATTR_WEATHER_TEMPERATURE: ('Temperature', '°C', 'T °C', float),
    'precipitation': ('Precipitation', 'l/m²', 'N l/m²', float),
    'dewpoint': ('Dew Point', '°C', 'TP °C', float),
    # The following probably not useful for general consumption,
    # but we need them to fill in internal attributes
    'station_name': ('Station Name', None, 'Name', str),
    'station_elevation': ('Station Elevation', 'm', 'Höhe m', int),
    'update_date': ('Update Date', None, 'Datum', str),
    'update_time': ('Update Time', None, 'Zeit', str),
}

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MONITORED_CONDITIONS, default=['temperature']):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Optional(CONF_STATION_ID): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Inclusive(CONF_LATITUDE, 'coordinates',
                  'Latitude and longitude must exist together'): cv.latitude,
    vol.Inclusive(CONF_LONGITUDE, 'coordinates',
                  'Latitude and longitude must exist together'): cv.longitude,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the ZAMG sensor platform."""
    name = config.get(CONF_NAME)
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)

    station_id = config.get(CONF_STATION_ID) or closest_station(
        latitude, longitude, hass.config.config_dir)
    if station_id not in zamg_stations(hass.config.config_dir):
        _LOGGER.error("Configured ZAMG %s (%s) is not a known station",
                      CONF_STATION_ID, station_id)
        return False

    probe = ZamgData(station_id=station_id)
    try:
        probe.update()
    except (ValueError, TypeError) as err:
        _LOGGER.error("Received error from ZAMG: %s", err)
        return False

    add_devices([ZamgSensor(probe, variable, name)
                 for variable in config[CONF_MONITORED_CONDITIONS]], True)


class ZamgSensor(Entity):
    """Implementation of a ZAMG sensor."""

    def __init__(self, probe, variable, name):
        """Initialize the sensor."""
        self.probe = probe
        self.client_name = name
        self.variable = variable

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self.client_name, self.variable)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.probe.get_data(self.variable)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return SENSOR_TYPES[self.variable][1]

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_WEATHER_ATTRIBUTION: ATTRIBUTION,
            ATTR_STATION: self.probe.get_data('station_name'),
            ATTR_UPDATED: self.probe.last_update.isoformat(),
        }

    def update(self):
        """Delegate update to probe."""
        self.probe.update()


class ZamgData(object):
    """The class for handling the data retrieval."""

    API_URL = 'http://www.zamg.ac.at/ogd/'
    API_HEADERS = {
        USER_AGENT: '{} {}'.format('home-assistant.zamg/', __version__),
    }

    def __init__(self, station_id):
        """Initialize the probe."""
        self._station_id = station_id
        self.data = {}

    @property
    def last_update(self):
        """Return the timestamp of the most recent data."""
        date, time = self.data.get('update_date'), self.data.get('update_time')
        if date is not None and time is not None:
            return datetime.strptime(date + time, '%d-%m-%Y%H:%M').replace(
                tzinfo=pytz.timezone('Europe/Vienna'))

    @classmethod
    def current_observations(cls):
        """Fetch the latest CSV data."""
        try:
            response = requests.get(
                cls.API_URL, headers=cls.API_HEADERS, timeout=15)
            response.raise_for_status()
            response.encoding = 'UTF8'
            return csv.DictReader(
                response.text.splitlines(), delimiter=';', quotechar='"')
        except requests.exceptions.HTTPError:
            _LOGGER.error("While fetching data")

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from ZAMG."""
        if self.last_update and (self.last_update + timedelta(hours=1) >
                                 datetime.utcnow().replace(tzinfo=pytz.utc)):
            return  # Not time to update yet; data is only hourly

        for row in self.current_observations():
            if row.get('Station') == self._station_id:
                api_fields = {col_heading: (standard_name, dtype)
                              for standard_name, (_, _, col_heading, dtype)
                              in SENSOR_TYPES.items()}
                self.data = {
                    api_fields.get(col_heading)[0]:
                        api_fields.get(col_heading)[1](v.replace(',', '.'))
                    for col_heading, v in row.items()
                    if col_heading in api_fields and v}
                break
        else:
            raise ValueError(
                "No weather data for station {}".format(self._station_id))

    def get_data(self, variable):
        """Get the data."""
        return self.data.get(variable)


def _get_zamg_stations():
    """Return {CONF_STATION: (lat, lon)} for all stations, for auto-config."""
    capital_stations = {r['Station'] for r in ZamgData.current_observations()}
    req = requests.get('https://www.zamg.ac.at/cms/en/documents/climate/'
                       'doc_metnetwork/zamg-observation-points', timeout=15)
    stations = {}
    for row in csv.DictReader(req.text.splitlines(),
                              delimiter=';', quotechar='"'):
        if row.get('synnr') in capital_stations:
            try:
                stations[row['synnr']] = tuple(
                    float(row[coord].replace(',', '.'))
                    for coord in ['breite_dezi', 'länge_dezi'])
            except KeyError:
                _LOGGER.error(
                    "ZAMG schema changed again, cannot autodetect station")
    return stations


def zamg_stations(cache_dir):
    """Return {CONF_STATION: (lat, lon)} for all stations, for auto-config.

    Results from internet requests are cached as compressed json, making
    subsequent calls very much faster.
    """
    cache_file = os.path.join(cache_dir, '.zamg-stations.json.gz')
    if not os.path.isfile(cache_file):
        stations = _get_zamg_stations()
        with gzip.open(cache_file, 'wt') as cache:
            json.dump(stations, cache, sort_keys=True)
        return stations
    with gzip.open(cache_file, 'rt') as cache:
        return {k: tuple(v) for k, v in json.load(cache).items()}


def closest_station(lat, lon, cache_dir):
    """Return the ZONE_ID.WMO_ID of the closest station to our lat/lon."""
    if lat is None or lon is None or not os.path.isdir(cache_dir):
        return
    stations = zamg_stations(cache_dir)

    def comparable_dist(zamg_id):
        """Calculate the psudeo-distance from lat/lon."""
        station_lat, station_lon = stations[zamg_id]
        return (lat - station_lat) ** 2 + (lon - station_lon) ** 2

    return min(stations, key=comparable_dist)
