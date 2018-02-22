"""
Support for Australian BOM (Bureau of Meteorology) weather service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.bom/
"""
import datetime
import ftplib
import gzip
import io
import json
import logging
import os
import re
import zipfile

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS, TEMP_CELSIUS, STATE_UNKNOWN, CONF_NAME,
    ATTR_ATTRIBUTION, CONF_LATITUDE, CONF_LONGITUDE)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

_RESOURCE = 'http://www.bom.gov.au/fwo/{}/{}.{}.json'
_LOGGER = logging.getLogger(__name__)

CONF_ATTRIBUTION = "Data provided by the Australian Bureau of Meteorology"
CONF_STATION = 'station'
CONF_ZONE_ID = 'zone_id'
CONF_WMO_ID = 'wmo_id'

MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(seconds=60)
LAST_UPDATE = 0

# Sensor types are defined like: Name, units
SENSOR_TYPES = {
    'wmo': ['wmo', None],
    'name': ['Station Name', None],
    'history_product': ['Zone', None],
    'local_date_time': ['Local Time', None],
    'local_date_time_full': ['Local Time Full', None],
    'aifstime_utc': ['UTC Time Full', None],
    'lat': ['Lat', None],
    'lon': ['Long', None],
    'apparent_t': ['Feels Like C', TEMP_CELSIUS],
    'cloud': ['Cloud', None],
    'cloud_base_m': ['Cloud Base', None],
    'cloud_oktas': ['Cloud Oktas', None],
    'cloud_type_id': ['Cloud Type ID', None],
    'cloud_type': ['Cloud Type', None],
    'delta_t': ['Delta Temp C', TEMP_CELSIUS],
    'gust_kmh': ['Wind Gust kmh', 'km/h'],
    'gust_kt': ['Wind Gust kt', 'kt'],
    'air_temp': ['Air Temp C', TEMP_CELSIUS],
    'dewpt': ['Dew Point C', TEMP_CELSIUS],
    'press': ['Pressure mb', 'mbar'],
    'press_qnh': ['Pressure qnh', 'qnh'],
    'press_msl': ['Pressure msl', 'msl'],
    'press_tend': ['Pressure Tend', None],
    'rain_trace': ['Rain Today', 'mm'],
    'rel_hum': ['Relative Humidity', '%'],
    'sea_state': ['Sea State', None],
    'swell_dir_worded': ['Swell Direction', None],
    'swell_height': ['Swell Height', 'm'],
    'swell_period': ['Swell Period', None],
    'vis_km': ['Visability km', 'km'],
    'weather': ['Weather', None],
    'wind_dir': ['Wind Direction', None],
    'wind_spd_kmh': ['Wind Speed kmh', 'km/h'],
    'wind_spd_kt': ['Wind Direction kt', 'kt']
}


def validate_station(station):
    """Check that the station ID is well-formed."""
    if station is None:
        return
    station = station.replace('.shtml', '')
    if not re.fullmatch(r'ID[A-Z]\d\d\d\d\d\.\d\d\d\d\d', station):
        raise vol.error.Invalid('Malformed station ID')
    return station


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Inclusive(CONF_ZONE_ID, 'Deprecated partial station ID'): cv.string,
    vol.Inclusive(CONF_WMO_ID, 'Deprecated partial station ID'): cv.string,
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_STATION): validate_station,
    vol.Required(CONF_MONITORED_CONDITIONS, default=[]):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the BOM sensor."""
    station = config.get(CONF_STATION)
    zone_id, wmo_id = config.get(CONF_ZONE_ID), config.get(CONF_WMO_ID)
    if station is not None:
        if zone_id and wmo_id:
            _LOGGER.warning(
                "Using config %s, not %s and %s for BOM sensor",
                CONF_STATION, CONF_ZONE_ID, CONF_WMO_ID)
    elif zone_id and wmo_id:
        station = '{}.{}'.format(zone_id, wmo_id)
    else:
        station = closest_station(
            config.get(CONF_LATITUDE), config.get(CONF_LONGITUDE),
            hass.config.config_dir)
        if station is None:
            _LOGGER.error("Could not get BOM weather station from lat/lon")
            return False

    rest = BOMCurrentData(hass, station)
    try:
        rest.update()
    except ValueError as err:
        _LOGGER.error("Received error from BOM_Current: %s", err)
        return False
    add_devices([BOMCurrentSensor(rest, variable, config.get(CONF_NAME))
                 for variable in config[CONF_MONITORED_CONDITIONS]])
    return True


class BOMCurrentSensor(Entity):
    """Implementation of a BOM current sensor."""

    def __init__(self, rest, condition, stationname):
        """Initialize the sensor."""
        self.rest = rest
        self._condition = condition
        self.stationname = stationname

    @property
    def name(self):
        """Return the name of the sensor."""
        if self.stationname is None:
            return 'BOM {}'.format(SENSOR_TYPES[self._condition][0])

        return 'BOM {} {}'.format(
            self.stationname, SENSOR_TYPES[self._condition][0])

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.rest.data and self._condition in self.rest.data:
            return self.rest.data[self._condition]

        return STATE_UNKNOWN

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {}
        attr['Sensor Id'] = self._condition
        attr['Zone Id'] = self.rest.data['history_product']
        attr['Station Id'] = self.rest.data['wmo']
        attr['Station Name'] = self.rest.data['name']
        attr['Last Update'] = datetime.datetime.strptime(str(
            self.rest.data['local_date_time_full']), '%Y%m%d%H%M%S')
        attr[ATTR_ATTRIBUTION] = CONF_ATTRIBUTION
        return attr

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return SENSOR_TYPES[self._condition][1]

    def update(self):
        """Update current conditions."""
        self.rest.update()


class BOMCurrentData(object):
    """Get data from BOM."""

    def __init__(self, hass, station_id):
        """Initialize the data object."""
        self._hass = hass
        self._zone_id, self._wmo_id = station_id.split('.')
        self.data = None
        self._lastupdate = LAST_UPDATE

    def _build_url(self):
        url = _RESOURCE.format(self._zone_id, self._zone_id, self._wmo_id)
        _LOGGER.info("BOM URL %s", url)
        return url

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from BOM."""
        if self._lastupdate != 0 and \
            ((datetime.datetime.now() - self._lastupdate) <
             datetime.timedelta(minutes=35)):
            _LOGGER.info(
                "BOM was updated %s minutes ago, skipping update as"
                " < 35 minutes", (datetime.datetime.now() - self._lastupdate))
            return self._lastupdate

        try:
            result = requests.get(self._build_url(), timeout=10).json()
            self.data = result['observations']['data'][0]
            self._lastupdate = datetime.datetime.strptime(
                str(self.data['local_date_time_full']), '%Y%m%d%H%M%S')
            return self._lastupdate
        except ValueError as err:
            _LOGGER.error("Check BOM %s", err.args)
            self.data = None
            raise


def _get_bom_stations():
    """Return {CONF_STATION: (lat, lon)} for all stations, for auto-config.

    This function does several MB of internet requests, so please use the
    caching version to minimise latency and hit-count.
    """
    latlon = {}
    with io.BytesIO() as file_obj:
        with ftplib.FTP('ftp.bom.gov.au') as ftp:
            ftp.login()
            ftp.cwd('anon2/home/ncc/metadata/sitelists')
            ftp.retrbinary('RETR stations.zip', file_obj.write)
        file_obj.seek(0)
        with zipfile.ZipFile(file_obj) as zipped:
            with zipped.open('stations.txt') as station_txt:
                for _ in range(4):
                    station_txt.readline()  # skip header
                while True:
                    line = station_txt.readline().decode().strip()
                    if len(line) < 120:
                        break  # end while loop, ignoring any footer text
                    wmo, lat, lon = (line[a:b].strip() for a, b in
                                     [(128, 134), (70, 78), (79, 88)])
                    if wmo != '..':
                        latlon[wmo] = (float(lat), float(lon))
    zones = {}
    pattern = (r'<a href="/products/(?P<zone>ID[A-Z]\d\d\d\d\d)/'
               r'(?P=zone)\.(?P<wmo>\d\d\d\d\d).shtml">')
    for state in ('nsw', 'vic', 'qld', 'wa', 'tas', 'nt'):
        url = 'http://www.bom.gov.au/{0}/observations/{0}all.shtml'.format(
            state)
        for zone_id, wmo_id in re.findall(pattern, requests.get(url).text):
            zones[wmo_id] = zone_id
    return {'{}.{}'.format(zones[k], k): latlon[k]
            for k in set(latlon) & set(zones)}


def bom_stations(cache_dir):
    """Return {CONF_STATION: (lat, lon)} for all stations, for auto-config.

    Results from internet requests are cached as compressed json, making
    subsequent calls very much faster.
    """
    cache_file = os.path.join(cache_dir, '.bom-stations.json.gz')
    if not os.path.isfile(cache_file):
        stations = _get_bom_stations()
        with gzip.open(cache_file, 'wt') as cache:
            json.dump(stations, cache, sort_keys=True)
        return stations
    with gzip.open(cache_file, 'rt') as cache:
        return {k: tuple(v) for k, v in json.load(cache).items()}


def closest_station(lat, lon, cache_dir):
    """Return the ZONE_ID.WMO_ID of the closest station to our lat/lon."""
    if lat is None or lon is None or not os.path.isdir(cache_dir):
        return
    stations = bom_stations(cache_dir)

    def comparable_dist(wmo_id):
        """Create a psudeo-distance from lat/lon."""
        station_lat, station_lon = stations[wmo_id]
        return (lat - station_lat) ** 2 + (lon - station_lon) ** 2

    return min(stations, key=comparable_dist)
