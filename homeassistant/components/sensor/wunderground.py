"""Support for Wunderground weather service."""
from datetime import timedelta
import logging
import requests

import voluptuous as vol

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.config_validation import ensure_list
from homeassistant.util import Throttle
from homeassistant.const import (CONF_PLATFORM, CONF_MONITORED_CONDITIONS,
                                 CONF_API_KEY, TEMP_FAHRENHEIT, TEMP_CELSIUS,
                                 STATE_UNKNOWN)

CONF_PWS_ID = 'pws_id'

_URL_QUERY = '/conditions/q/'
_RESOURCE = 'http://api.wunderground.com/api/'
_LOGGER = logging.getLogger(__name__)

# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=300)

# Sensor types are defined like: Name, units
SENSOR_TYPES = {
    'weather': ['Weather Summary', None],
    'station_id': ['Station ID', None],
    'feelslike_c': ['Feels Like (°C)', TEMP_CELSIUS],
    'feelslike_f': ['Feels Like (°F)', TEMP_FAHRENHEIT],
    'feelslike_string': ['Feels Like', None],
    'heat_index_c': ['Dewpoint (°C)', TEMP_CELSIUS],
    'heat_index_f': ['Dewpoint (°F)', TEMP_FAHRENHEIT],
    'heat_index_string': ['Heat Index Summary', None],
    'dewpoint_c': ['Dewpoint (°C)', TEMP_CELSIUS],
    'dewpoint_f': ['Dewpoint (°F)', TEMP_FAHRENHEIT],
    'dewpoint_string': ['Dewpoint Summary', None],
    'wind_kph': ['Wind Speed', 'kpH'],
    'wind_mph': ['Wind Speed', 'mpH'],
    'UV': ['UV', None],
    'pressure_in': ['Pressure', 'in'],
    'pressure_mb': ['Pressure', 'mbar'],
    'wind_dir': ['Wind Direction', None],
    'wind_string': ['Wind Summary', None],
    'temp_c': ['Temperature (°C)', TEMP_CELSIUS],
    'temp_f': ['Temperature (°F)', TEMP_FAHRENHEIT],
    'relative_humidity': ['Relative Humidity', '%'],
    'visibility_mi': ['Visibility (miles)', 'mi'],
    'visibility_km': ['Visibility (km)', 'km'],
    'precip_today_in': ['Precipation Today', 'in'],
    'precip_today_metric': ['Precipitation Today', 'mm'],
    'precip_today_string': ['Precipitation today', None],
    'solarradiation': ['Solar Radiation', None]
}

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): "wunderground",
    vol.Required(CONF_API_KEY): vol.Coerce(str),
    CONF_PWS_ID: vol.Coerce(str),
    vol.Required(CONF_MONITORED_CONDITIONS, default=[]): ensure_list,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Wunderground sensor."""
    if not PLATFORM_SCHEMA(config):
        return False

    rest = WUndergroundData(hass,
                            config.get(CONF_API_KEY),
                            config.get(CONF_PWS_ID, None))
    sensors = []
    for variable in config['monitored_conditions']:
        if variable in SENSOR_TYPES:
            sensors.append(WUndergroundSensor(rest, variable))
        else:
            _LOGGER.error('Wunderground sensor: "%s" does not exist', variable)

    try:
        rest.update()
    except ValueError as err:
        _LOGGER.error("Received error from WUnderground: %s", err)
        return False

    add_devices(sensors)

    return True


class WUndergroundSensor(Entity):
    """Implementing the Wunderground sensor."""

    def __init__(self, rest, condition):
        """Initialize the sensor."""
        self.rest = rest
        self._condition = condition
        self._unit_of_measurement = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return "PWS_" + self._condition

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.rest.data and self._condition in self.rest.data:
            return self.rest.data[self._condition]
        else:
            return STATE_UNKNOWN

    @property
    def entity_picture(self):
        """Return the entity picture."""
        if self._condition == 'weather':
            return self.rest.data['icon_url']

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return SENSOR_TYPES[self._condition][1]

    def update(self):
        """Update current conditions."""
        self.rest.update()

# pylint: disable=too-few-public-methods


class WUndergroundData(object):
    """Get data from Wundeground."""

    def __init__(self, hass, api_key, pws_id=None):
        """Initialize the data object."""
        self._hass = hass
        self._api_key = api_key
        self._pws_id = pws_id
        self._latitude = hass.config.latitude
        self._longitude = hass.config.longitude
        self.data = None

    def _build_url(self):
        print(self._api_key)
        url = _RESOURCE + self._api_key + _URL_QUERY
        if self._pws_id:
            url = url + 'pws:' + self._pws_id
        else:
            url = url + '{},{}'.format(self._latitude, self._longitude)

        return url + '.json'

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from wunderground."""
        try:
            result = requests.get(self._resource + self._api_key +
                                  '/conditions/q/pws:' + self._pws_id +
                                  '.json', timeout=10)
            if "error" in result.json():
                raise ValueError(result.json()["response"]["error"]
                                 ["description"])
            else:
                self.data = result.json()["current_observation"]
        except ValueError as err:
            _LOGGER.error("Check Wunderground API %s", err.args)
            self.data = None
