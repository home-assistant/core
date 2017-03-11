"""
Support for WUnderground weather service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.wunderground/
"""
from datetime import timedelta
import logging

import re
import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS, CONF_API_KEY, TEMP_FAHRENHEIT, TEMP_CELSIUS,
    STATE_UNKNOWN, ATTR_ATTRIBUTION)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

_RESOURCE = 'http://api.wunderground.com/api/{}/conditions/{}/q/'
_ALERTS = 'http://api.wunderground.com/api/{}/alerts/{}/q/'
_LOGGER = logging.getLogger(__name__)

CONF_ATTRIBUTION = "Data provided by the WUnderground weather service"
CONF_PWS_ID = 'pws_id'
CONF_LANG = 'lang'

DEFAULT_LANG = 'EN'

MIN_TIME_BETWEEN_UPDATES_ALERTS = timedelta(minutes=15)
MIN_TIME_BETWEEN_UPDATES_OBSERVATION = timedelta(minutes=5)

# Sensor types are defined like: Name, units
SENSOR_TYPES = {
    'alerts': ['Alerts', None],
    'dewpoint_c': ['Dewpoint (°C)', TEMP_CELSIUS],
    'dewpoint_f': ['Dewpoint (°F)', TEMP_FAHRENHEIT],
    'dewpoint_string': ['Dewpoint Summary', None],
    'feelslike_c': ['Feels Like (°C)', TEMP_CELSIUS],
    'feelslike_f': ['Feels Like (°F)', TEMP_FAHRENHEIT],
    'feelslike_string': ['Feels Like', None],
    'heat_index_c': ['Dewpoint (°C)', TEMP_CELSIUS],
    'heat_index_f': ['Dewpoint (°F)', TEMP_FAHRENHEIT],
    'heat_index_string': ['Heat Index Summary', None],
    'elevation': ['Elevation', 'ft'],
    'location': ['Location', None],
    'observation_time': ['Observation Time', None],
    'precip_1hr_in': ['Precipation 1hr', 'in'],
    'precip_1hr_metric': ['Precipation 1hr', 'mm'],
    'precip_1hr_string': ['Precipation 1hr', None],
    'precip_today_in': ['Precipation Today', 'in'],
    'precip_today_metric': ['Precipitation Today', 'mm'],
    'precip_today_string': ['Precipitation today', None],
    'pressure_in': ['Pressure', 'in'],
    'pressure_mb': ['Pressure', 'mb'],
    'pressure_trend': ['Pressure Trend', None],
    'relative_humidity': ['Relative Humidity', '%'],
    'station_id': ['Station ID', None],
    'solarradiation': ['Solar Radiation', None],
    'temperature_string': ['Temperature Summary', None],
    'temp_c': ['Temperature (°C)', TEMP_CELSIUS],
    'temp_f': ['Temperature (°F)', TEMP_FAHRENHEIT],
    'UV': ['UV', None],
    'visibility_km': ['Visibility (km)', 'km'],
    'visibility_mi': ['Visibility (miles)', 'mi'],
    'weather': ['Weather Summary', None],
    'wind_degrees': ['Wind Degrees', None],
    'wind_dir': ['Wind Direction', None],
    'wind_gust_kph': ['Wind Gust', 'kph'],
    'wind_gust_mph': ['Wind Gust', 'mph'],
    'wind_kph': ['Wind Speed', 'kph'],
    'wind_mph': ['Wind Speed', 'mph'],
    'wind_string': ['Wind Summary', None],
}

# Alert Attributes
ALERTS_ATTRS = [
    'date',
    'description',
    'expires',
    'message',
]

# Language Supported Codes
LANG_CODES = [
    'AF', 'AL', 'AR', 'HY', 'AZ', 'EU',
    'BY', 'BU', 'LI', 'MY', 'CA', 'CN',
    'TW', 'CR', 'CZ', 'DK', 'DV', 'NL',
    'EN', 'EO', 'ET', 'FA', 'FI', 'FR',
    'FC', 'GZ', 'DL', 'KA', 'GR', 'GU',
    'HT', 'IL', 'HI', 'HU', 'IS', 'IO',
    'ID', 'IR', 'IT', 'JP', 'JW', 'KM',
    'KR', 'KU', 'LA', 'LV', 'LT', 'ND',
    'MK', 'MT', 'GM', 'MI', 'MR', 'MN',
    'NO', 'OC', 'PS', 'GN', 'PL', 'BR',
    'PA', 'PU', 'RO', 'RU', 'SR', 'SK',
    'SL', 'SP', 'SI', 'SW', 'CH', 'TL',
    'TT', 'TH', 'UA', 'UZ', 'VU', 'CY',
    'SN', 'JI', 'YI',
]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Optional(CONF_PWS_ID): cv.string,
    vol.Optional(CONF_LANG, default=DEFAULT_LANG):
        vol.All(vol.In(LANG_CODES)),
    vol.Required(CONF_MONITORED_CONDITIONS, default=[]):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the WUnderground sensor."""
    rest = WUndergroundData(hass,
                            config.get(CONF_API_KEY),
                            config.get(CONF_PWS_ID),
                            config.get(CONF_LANG))
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
        if self.rest.data:

            if self._condition == 'elevation' and self._condition in \
                    self.rest.data['observation_location']:
                return self.rest.data['observation_location'][self._condition]\
                        .split()[0]

            if self._condition == 'location' and \
               'full' in self.rest.data['display_location']:
                return self.rest.data['display_location']['full']

            if self._condition in self.rest.data:
                if self._condition == 'relative_humidity':
                    return int(self.rest.data[self._condition][:-1])
                else:
                    return self.rest.data[self._condition]

        if self._condition == 'alerts':
            if self.rest.alerts:
                return len(self.rest.alerts)
            else:
                return 0
        return STATE_UNKNOWN

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {}

        attrs[ATTR_ATTRIBUTION] = CONF_ATTRIBUTION

        if not self.rest.alerts or self._condition != 'alerts':
            return attrs

        multiple_alerts = len(self.rest.alerts) > 1
        for data in self.rest.alerts:
            for alert in ALERTS_ATTRS:
                if data[alert]:
                    if multiple_alerts:
                        dkey = alert.capitalize() + '_' + data['type']
                    else:
                        dkey = alert.capitalize()
                    attrs[dkey] = data[alert]
        return attrs

    @property
    def entity_picture(self):
        """Return the entity picture."""
        if self.rest.data and self._condition == 'weather':
            url = self.rest.data['icon_url']
            return re.sub(r'^http://', 'https://', url, flags=re.IGNORECASE)

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return SENSOR_TYPES[self._condition][1]

    def update(self):
        """Update current conditions."""
        if self._condition == 'alerts':
            self.rest.update_alerts()
        else:
            self.rest.update()


class WUndergroundData(object):
    """Get data from WUnderground."""

    def __init__(self, hass, api_key, pws_id, lang):
        """Initialize the data object."""
        self._hass = hass
        self._api_key = api_key
        self._pws_id = pws_id
        self._lang = 'lang:{}'.format(lang)
        self._latitude = hass.config.latitude
        self._longitude = hass.config.longitude
        self.data = None
        self.alerts = None

    def _build_url(self, baseurl=_RESOURCE):
        url = baseurl.format(self._api_key, self._lang)
        if self._pws_id:
            url = url + 'pws:{}'.format(self._pws_id)
        else:
            url = url + '{},{}'.format(self._latitude, self._longitude)

        return url + '.json'

    @Throttle(MIN_TIME_BETWEEN_UPDATES_OBSERVATION)
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

    @Throttle(MIN_TIME_BETWEEN_UPDATES_ALERTS)
    def update_alerts(self):
        """Get the latest alerts data from WUnderground."""
        try:
            result = requests.get(self._build_url(_ALERTS), timeout=10).json()
            if "error" in result['response']:
                raise ValueError(result['response']["error"]
                                 ["description"])
            else:
                self.alerts = result["alerts"]
        except ValueError as err:
            _LOGGER.error("Check WUnderground API %s", err.args)
            self.alerts = None
