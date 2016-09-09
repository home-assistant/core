"""
Support for WUnderground weather service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.wunderground/
"""
from datetime import timedelta
import logging

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS, CONF_API_KEY, TEMP_FAHRENHEIT, TEMP_CELSIUS,
    STATE_UNKNOWN)

_RESOURCE = 'http://api.wunderground.com/api/{}/conditions/q/'
_LOGGER = logging.getLogger(__name__)

CONF_PWS_ID = 'pws_id'

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

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Optional(CONF_PWS_ID): cv.string,
    vol.Required(CONF_MONITORED_CONDITIONS, default=[]):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the WUnderground sensor."""
    rest = WUndergroundData(hass,
                            config.get(CONF_API_KEY),
                            config.get(CONF_PWS_ID, None))
    sensors = []
    for variable in config[CONF_MONITORED_CONDITIONS]:
        sensors.append(WUndergroundSensor(rest, variable))

    try:
        rest.update()
    except ValueError as err:
        _LOGGER.error("Received error from WUnderground: %s", err)
        return False

    add_devices(sensors)

    return True


class WUndergroundSensor(Entity):
    """Implementing the WUnderground sensor."""

    def __init__(self, rest, condition):
        """Initialize the sensor."""
        self.rest = rest
        self._condition = condition

    @property
    def name(self):
        """Return the name of the sensor."""
        return "PWS_" + self._condition

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.rest.data and self._condition in self.rest.data:
            if self._condition == 'relative_humidity':
                return int(self.rest.data[self._condition][:-1])
            else:
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
    """Get data from WUnderground."""

    def __init__(self, hass, api_key, pws_id=None):
        """Initialize the data object."""
        self._hass = hass
        self._api_key = api_key
        self._pws_id = pws_id
        self._latitude = hass.config.latitude
        self._longitude = hass.config.longitude
        self.data = None

    def _build_url(self):
        url = _RESOURCE.format(self._api_key)
        if self._pws_id:
            url = url + 'pws:{}'.format(self._pws_id)
        else:
            url = url + '{},{}'.format(self._latitude, self._longitude)

        return url + '.json'

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from WUnderground."""
        try:
            result = requests.get(self._build_url(), timeout=10).json()
            if "error" in result['response']:
                raise ValueError(result['response']["error"]
                                 ["description"])
            else:
                self.data = result["current_observation"]
        except ValueError as err:
            _LOGGER.error("Check WUnderground API %s", err.args)
            self.data = None
            raise
