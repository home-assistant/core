"""
Support for UK Met Office weather service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.metoffice/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS, TEMP_CELSIUS, STATE_UNKNOWN, CONF_NAME,
    ATTR_ATTRIBUTION, CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['datapoint==0.4.3']

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

SCAN_INTERVAL = timedelta(minutes=35)

# Sensor types are defined like: Name, units
SENSOR_TYPES = {
    'name': ['Station Name', None],
    'weather': ['Weather', None],
    'temperature': ['Temperature', TEMP_CELSIUS],
    'feels_like_temperature': ['Feels Like Temperature', TEMP_CELSIUS],
    'wind_speed': ['Wind Speed', 'm/s'],
    'wind_direction': ['Wind Direction', None],
    'wind_gust': ['Wind Gust', 'm/s'],
    'visibility': ['Visibility', 'km'],
    'uv': ['UV', None],
    'precipitation': ['Probability of Precipitation', '%'],
    'humidity': ['Humidity', '%']
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=None): cv.string,
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_MONITORED_CONDITIONS, default=[]):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Metoffice sensor platform."""
    import datapoint as dp
    datapoint = dp.connection(api_key=config.get(CONF_API_KEY))

    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)

    if None in (latitude, longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return False

    try:
        site = datapoint.get_nearest_site(latitude=latitude,
                                          longitude=longitude)
    except dp.exceptions.APIException as err:
        _LOGGER.error("Received error from Met Office Datapoint: %s", err)
        return False

    if not site:
        _LOGGER.error("Unable to get nearest Met Office forecast site")
        return False

    # Get data
    data = MetOfficeCurrentData(hass, datapoint, site)
    try:
        data.update()
    except (ValueError, dp.exceptions.APIException) as err:
        _LOGGER.error("Received error from Met Office Datapoint: %s", err)
        return False

    # Add
    add_devices([MetOfficeCurrentSensor(site, data, variable)
                 for variable in config[CONF_MONITORED_CONDITIONS]])
    return True


class MetOfficeCurrentSensor(Entity):
    """Implementation of a Met Office current sensor."""

    def __init__(self, site, data, condition):
        """Initialize the sensor."""
        self.site = site
        self.data = data
        self._condition = condition

    @property
    def name(self):
        """Return the name of the sensor."""
        return 'Met Office {}'.format(SENSOR_TYPES[self._condition][0])

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._condition in self.data.data.__dict__.keys():
            variable = getattr(self.data.data, self._condition)
            if self._condition == "weather":
                return [k for k, v in CONDITION_CLASSES.items() if
                        self.data.data.weather.value in v][0]
            else:
                return variable.value
        else:
            return STATE_UNKNOWN

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return SENSOR_TYPES[self._condition][1]

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {}
        attr['Sensor Id'] = self._condition
        attr['Site Id'] = self.site.id
        attr['Site Name'] = self.site.name
        attr['Last Update'] = self.data.data.date
        attr[ATTR_ATTRIBUTION] = CONF_ATTRIBUTION
        return attr

    def update(self):
        """Update current conditions."""
        self.data.update()


class MetOfficeCurrentData(object):
    """Get data from Datapoint."""

    def __init__(self, hass, datapoint, site):
        """Initialize the data object."""
        self._hass = hass
        self._datapoint = datapoint
        self._site = site
        self.data = None

    @Throttle(SCAN_INTERVAL)
    def update(self):
        """Get the latest data from Datapoint."""
        import datapoint as dp

        try:
            forecast = self._datapoint.get_forecast_for_site(
                self._site.id, "3hourly")
            self.data = forecast.now()
        except (ValueError, dp.exceptions.APIException) as err:
            _LOGGER.error("Check Met Office %s", err.args)
            self.data = None
            raise
