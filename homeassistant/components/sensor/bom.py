"""
Support for bom.gov.au current condition weather service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.bom_weather_current/
"""

import datetime
import logging
import requests

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS, TEMP_CELSIUS,
    STATE_UNKNOWN, CONF_NAME)

_RESOURCE = 'http://www.bom.gov.au/fwo/{}/{}.{}.json'
_LOGGER = logging.getLogger(__name__)

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

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ZONE_ID): cv.string,
    vol.Required(CONF_WMO_ID): cv.string,
    vol.Optional(CONF_NAME, default=None): cv.string,
    vol.Required(CONF_MONITORED_CONDITIONS, default=[]):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the BOM sensor."""
    rest = BOMCurrentData(hass, config.get(CONF_ZONE_ID),
                          config.get(CONF_WMO_ID))
    sensors = []
    for variable in config[CONF_MONITORED_CONDITIONS]:
        sensors.append(BOMCurrentSensor(rest,
                                        variable,
                                        config.get(CONF_NAME)))

    try:
        rest.update()
    except ValueError as err:
        _LOGGER.error("Received error from BOM_Current: %s", err)
        return False

    add_devices(sensors)

    return True


class BOMCurrentSensor(Entity):
    """Implementing the BOM current sensor."""

    def __init__(self, rest, condition, stationname):
        """Initialize the sensor."""
        self.rest = rest
        self._condition = condition
        self.stationname = stationname

    @property
    def name(self):
        """Return the name of the sensor."""
        if self.stationname is None:
            return "BOM {}".format(SENSOR_TYPES[self._condition][0])
        else:
            return "BOM {} {}".format(self.stationname,
                                      SENSOR_TYPES[self._condition][0])

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.rest.data and self._condition in self.rest.data:
            return self.rest.data[self._condition]
        else:
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
        return attr

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return SENSOR_TYPES[self._condition][1]

    def update(self):
        """Update current conditions."""
        self.rest.update()


# pylint: disable=too-few-public-methods
class BOMCurrentData(object):
    """Get data from BOM."""

    def __init__(self, hass, zone_id, wmo_id):
        """Initialize the data object."""
        self._hass = hass
        self._zone_id = zone_id
        self._wmo_id = wmo_id
        self.data = None
        self._lastupdate = LAST_UPDATE

    def _build_url(self):
        url = _RESOURCE.format(self._zone_id, self._zone_id, self._wmo_id)
        _LOGGER.info("BOM url %s", url)
        return url

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from BOM."""
        if ((self._lastupdate != 0)
                and ((datetime.datetime.now() - self._lastupdate)) <
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
