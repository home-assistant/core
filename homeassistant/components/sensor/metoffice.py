"""
Support for UK Met Office weather service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.metoffice/
"""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE,
    CONF_MONITORED_CONDITIONS, CONF_NAME, TEMP_CELSIUS)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['datapoint==0.4.3']

ATTR_LAST_UPDATE = 'last_update'
ATTR_SENSOR_ID = 'sensor_id'
ATTR_SITE_ID = 'site_id'
ATTR_SITE_NAME = 'site_name'

CONF_ATTRIBUTION = "Data provided by the Met Office"

CONDITION_CLASSES = {
    'cloudy': ['7', '8'],
    'fog': ['5', '6'],
    'hail': ['19', '20', '21'],
    'lightning': ['30'],
    'lightning-rainy': ['28', '29'],
    'partlycloudy': ['2', '3'],
    'pouring': ['13', '14', '15'],
    'rainy': ['9', '10', '11', '12'],
    'snowy': ['22', '23', '24', '25', '26', '27'],
    'snowy-rainy': ['16', '17', '18'],
    'sunny': ['0', '1'],
    'windy': [],
    'windy-variant': [],
    'exceptional': [],
}

DEFAULT_NAME = "Met Office"

VISIBILITY_CLASSES = {
    'VP': '<1',
    'PO': '1-4',
    'MO': '4-10',
    'GO': '10-20',
    'VG': '20-40',
    'EX': '>40'
}

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=35)

# Sensor types are defined like: Name, units
SENSOR_TYPES = {
    'name': ['Station Name', None],
    'weather': ['Weather', None],
    'temperature': ['Temperature', TEMP_CELSIUS],
    'feels_like_temperature': ['Feels Like Temperature', TEMP_CELSIUS],
    'wind_speed': ['Wind Speed', 'mph'],
    'wind_direction': ['Wind Direction', None],
    'wind_gust': ['Wind Gust', 'mph'],
    'visibility': ['Visibility', None],
    'visibility_distance': ['Visibility Distance', 'km'],
    'uv': ['UV', None],
    'precipitation': ['Probability of Precipitation', '%'],
    'humidity': ['Humidity', '%']
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_MONITORED_CONDITIONS, default=[]):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Inclusive(CONF_LATITUDE, 'coordinates',
                  'Latitude and longitude must exist together'): cv.latitude,
    vol.Inclusive(CONF_LONGITUDE, 'coordinates',
                  'Latitude and longitude must exist together'): cv.longitude,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Met Office sensor platform."""
    import datapoint as dp

    api_key = config.get(CONF_API_KEY)
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    name = config.get(CONF_NAME)

    datapoint = dp.connection(api_key=api_key)

    if None in (latitude, longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return

    try:
        site = datapoint.get_nearest_site(
            latitude=latitude, longitude=longitude)
    except dp.exceptions.APIException as err:
        _LOGGER.error("Received error from Met Office Datapoint: %s", err)
        return

    if not site:
        _LOGGER.error("Unable to get nearest Met Office forecast site")
        return

    data = MetOfficeCurrentData(hass, datapoint, site)
    data.update()
    if data.data is None:
        return

    sensors = []
    for variable in config[CONF_MONITORED_CONDITIONS]:
        sensors.append(MetOfficeCurrentSensor(site, data, variable, name))

    add_devices(sensors, True)


class MetOfficeCurrentSensor(Entity):
    """Implementation of a Met Office current sensor."""

    def __init__(self, site, data, condition, name):
        """Initialize the sensor."""
        self._condition = condition
        self.data = data
        self._name = name
        self.site = site

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self._name, SENSOR_TYPES[self._condition][0])

    @property
    def state(self):
        """Return the state of the sensor."""
        if (self._condition == 'visibility_distance' and
                hasattr(self.data.data, 'visibility')):
            return VISIBILITY_CLASSES.get(self.data.data.visibility.value)
        if hasattr(self.data.data, self._condition):
            variable = getattr(self.data.data, self._condition)
            if self._condition == 'weather':
                return [k for k, v in CONDITION_CLASSES.items() if
                        self.data.data.weather.value in v][0]
            return variable.value
        return None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return SENSOR_TYPES[self._condition][1]

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {}
        attr[ATTR_ATTRIBUTION] = CONF_ATTRIBUTION
        attr[ATTR_LAST_UPDATE] = self.data.data.date
        attr[ATTR_SENSOR_ID] = self._condition
        attr[ATTR_SITE_ID] = self.site.id
        attr[ATTR_SITE_NAME] = self.site.name
        return attr

    def update(self):
        """Update current conditions."""
        self.data.update()


class MetOfficeCurrentData(object):
    """Get data from Datapoint."""

    def __init__(self, hass, datapoint, site):
        """Initialize the data object."""
        self._datapoint = datapoint
        self._site = site
        self.data = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from Datapoint."""
        import datapoint as dp

        try:
            forecast = self._datapoint.get_forecast_for_site(
                self._site.id, '3hourly')
            self.data = forecast.now()
        except (ValueError, dp.exceptions.APIException) as err:
            _LOGGER.error("Check Met Office %s", err.args)
            self.data = None
