"""
Support for Yr.no weather service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.yr/
"""
import logging
import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_PLATFORM, CONF_LATITUDE, CONF_LONGITUDE, CONF_ELEVATION,
    CONF_MONITORED_CONDITIONS
)
from homeassistant.helpers.entity import Entity
from homeassistant.util import dt as dt_util
from homeassistant.util import location

_LOGGER = logging.getLogger(__name__)


REQUIREMENTS = ['xmltodict']

# Sensor types are defined like so:
SENSOR_TYPES = {
    'symbol': ['Symbol', None],
    'precipitation': ['Condition', 'mm'],
    'temperature': ['Temperature', '°C'],
    'windSpeed': ['Wind speed', 'm/s'],
    'windGust': ['Wind gust', 'm/s'],
    'pressure': ['Pressure', 'hPa'],
    'windDirection': ['Wind direction', '°'],
    'humidity': ['Humidity', '%'],
    'fog': ['Fog', '%'],
    'cloudiness': ['Cloudiness', '%'],
    'lowClouds': ['Low clouds', '%'],
    'mediumClouds': ['Medium clouds', '%'],
    'highClouds': ['High clouds', '%'],
    'dewpointTemperature': ['Dewpoint temperature', '°C'],
}

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): 'yr',
    vol.Optional(CONF_MONITORED_CONDITIONS, default=[]):
        [vol.In(SENSOR_TYPES.keys())],
    vol.Optional(CONF_LATITUDE): cv.latitude,
    vol.Optional(CONF_LONGITUDE): cv.longitude,
    vol.Optional(CONF_ELEVATION): vol.Coerce(int),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Yr.no sensor."""
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    elevation = config.get(CONF_ELEVATION)

    if None in (latitude, longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return False

    if elevation is None:
        elevation = location.elevation(latitude,
                                       longitude)

    coordinates = dict(lat=latitude,
                       lon=longitude,
                       msl=elevation)

    weather = YrData(coordinates)

    dev = []
    for sensor_type in config[CONF_MONITORED_CONDITIONS]:
        dev.append(YrSensor(sensor_type, weather))

    # add symbol as default sensor
    if len(dev) == 0:
        dev.append(YrSensor("symbol", weather))
    add_devices(dev)


# pylint: disable=too-many-instance-attributes
class YrSensor(Entity):
    """Representation of an Yr.no sensor."""

    def __init__(self, sensor_type, weather):
        """Initialize the sensor."""
        self.client_name = 'yr'
        self._name = SENSOR_TYPES[sensor_type][0]
        self.type = sensor_type
        self._state = None
        self._weather = weather
        self._unit_of_measurement = SENSOR_TYPES[self.type][1]
        self._update = None

        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self.client_name, self._name)

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def entity_picture(self):
        """Weather symbol if type is symbol."""
        if self.type != 'symbol':
            return None
        return "//api.met.no/weatherapi/weathericon/1.1/" \
               "?symbol={0};content_type=image/png".format(self._state)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            'about': "Weather forecast from yr.no, delivered by the"
                     " Norwegian Meteorological Institute and the NRK"
        }

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    def update(self):
        """Get the latest data from yr.no and updates the states."""
        now = dt_util.utcnow()
        # Check if data should be updated
        if self._update is not None and now <= self._update:
            return

        self._weather.update()

        # Find sensor
        for time_entry in self._weather.data['product']['time']:
            valid_from = dt_util.parse_datetime(time_entry['@from'])
            valid_to = dt_util.parse_datetime(time_entry['@to'])

            loc_data = time_entry['location']

            if self.type not in loc_data or now >= valid_to:
                continue

            self._update = valid_to

            if self.type == 'precipitation' and valid_from < now:
                self._state = loc_data[self.type]['@value']
                break
            elif self.type == 'symbol' and valid_from < now:
                self._state = loc_data[self.type]['@number']
                break
            elif self.type in ('temperature', 'pressure', 'humidity',
                               'dewpointTemperature'):
                self._state = loc_data[self.type]['@value']
                break
            elif self.type in ('windSpeed', 'windGust'):
                self._state = loc_data[self.type]['@mps']
                break
            elif self.type == 'windDirection':
                self._state = float(loc_data[self.type]['@deg'])
                break
            elif self.type in ('fog', 'cloudiness', 'lowClouds',
                               'mediumClouds', 'highClouds'):
                self._state = loc_data[self.type]['@percent']
                break


# pylint: disable=too-few-public-methods
class YrData(object):
    """Get the latest data and updates the states."""

    def __init__(self, coordinates):
        """Initialize the data object."""
        self._url = 'http://api.yr.no/weatherapi/locationforecast/1.9/?' \
            'lat={lat};lon={lon};msl={msl}'.format(**coordinates)

        self._nextrun = None
        self.data = {}
        self.update()

    def update(self):
        """Get the latest data from yr.no."""
        # Check if new will be available
        if self._nextrun is not None and dt_util.utcnow() <= self._nextrun:
            return
        try:
            with requests.Session() as sess:
                response = sess.get(self._url)
        except requests.RequestException:
            return
        if response.status_code != 200:
            return
        data = response.text

        import xmltodict
        self.data = xmltodict.parse(data)['weatherdata']
        model = self.data['meta']['model']
        if '@nextrun' not in model:
            model = model[0]
        self._nextrun = dt_util.parse_datetime(model['@nextrun'])
