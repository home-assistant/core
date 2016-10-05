"""
Support for Dark Sky weather service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.darksky/
"""
import logging
from datetime import timedelta

import voluptuous as vol
from requests.exceptions import ConnectionError as ConnectError, \
    HTTPError, Timeout

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_API_KEY, CONF_NAME, CONF_MONITORED_CONDITIONS)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['python-forecastio==1.3.5']

_LOGGER = logging.getLogger(__name__)

CONF_UNITS = 'units'
CONF_UPDATE_INTERVAL = 'update_interval'

DEFAULT_NAME = 'Dark Sky'

# Sensor types are defined like so:
# Name, si unit, us unit, ca unit, uk unit, uk2 unit
SENSOR_TYPES = {
    'summary': ['Summary', None, None, None, None, None, None],
    'minutely_summary': ['Minutely Summary',
                         None, None, None, None, None, None],
    'hourly_summary': ['Hourly Summary', None, None, None, None, None, None],
    'daily_summary': ['Daily Summary', None, None, None, None, None, None],
    'icon': ['Icon', None, None, None, None, None, None],
    'nearest_storm_distance': ['Nearest Storm Distance',
                               'km', 'm', 'km', 'km', 'm',
                               'mdi:weather-lightning'],
    'nearest_storm_bearing': ['Nearest Storm Bearing',
                              '°', '°', '°', '°', '°',
                              'mdi:weather-lightning'],
    'precip_type': ['Precip', None, None, None, None, None,
                    'mdi:weather-pouring'],
    'precip_intensity': ['Precip Intensity',
                         'mm', 'in', 'mm', 'mm', 'mm', 'mdi:weather-rainy'],
    'precip_probability': ['Precip Probability',
                           '%', '%', '%', '%', '%', 'mdi:water-percent'],
    'temperature': ['Temperature',
                    '°C', '°F', '°C', '°C', '°C', 'mdi:thermometer'],
    'apparent_temperature': ['Apparent Temperature',
                             '°C', '°F', '°C', '°C', '°C', 'mdi:thermometer'],
    'dew_point': ['Dew point', '°C', '°F', '°C', '°C', '°C',
                  'mdi:thermometer'],
    'wind_speed': ['Wind Speed', 'm/s', 'mph', 'km/h', 'mph', 'mph',
                   'mdi:weather-windy'],
    'wind_bearing': ['Wind Bearing', '°', '°', '°', '°', '°', 'mdi:compass'],
    'cloud_cover': ['Cloud Coverage', '%', '%', '%', '%', '%',
                    'mdi:weather-partlycloudy'],
    'humidity': ['Humidity', '%', '%', '%', '%', '%', 'mdi:water-percent'],
    'pressure': ['Pressure', 'mbar', 'mbar', 'mbar', 'mbar', 'mbar',
                 'mdi:gauge'],
    'visibility': ['Visibility', 'km', 'm', 'km', 'km', 'm', 'mdi:eye'],
    'ozone': ['Ozone', 'DU', 'DU', 'DU', 'DU', 'DU', 'mdi:eye'],
    'apparent_temperature_max': ['Daily High Apparent Temperature',
                                 '°C', '°F', '°C', '°C', '°C',
                                 'mdi:thermometer'],
    'apparent_temperature_min': ['Daily Low Apparent Temperature',
                                 '°C', '°F', '°C', '°C', '°C',
                                 'mdi:thermometer'],
    'temperature_max': ['Daily High Temperature',
                        '°C', '°F', '°C', '°C', '°C', 'mdi:thermometer'],
    'temperature_min': ['Daily Low Temperature',
                        '°C', '°F', '°C', '°C', '°C', 'mdi:thermometer'],
    'precip_intensity_max': ['Daily Max Precip Intensity',
                             'mm', 'in', 'mm', 'mm', 'mm', 'mdi:thermometer'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MONITORED_CONDITIONS):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Required(CONF_API_KEY): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_UNITS): vol.In(['auto', 'si', 'us', 'ca', 'uk', 'uk2']),
    vol.Optional(CONF_UPDATE_INTERVAL, default=timedelta(seconds=120)): (
        vol.All(cv.time_period, cv.positive_timedelta)),
})


# pylint: disable=too-many-arguments
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Dark Sky sensor."""
    # Validate the configuration
    if None in (hass.config.latitude, hass.config.longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return False

    if CONF_UNITS in config:
        units = config[CONF_UNITS]
    elif hass.config.units.is_metric:
        units = 'si'
    else:
        units = 'us'

    # Create a data fetcher to support all of the configured sensors. Then make
    # the first call to init the data and confirm we can connect.
    try:
        forecast_data = DarkSkyData(
            api_key=config.get(CONF_API_KEY, None),
            latitude=hass.config.latitude,
            longitude=hass.config.longitude,
            units=units,
            interval=config.get(CONF_UPDATE_INTERVAL))
        forecast_data.update_currently()
    except ValueError as error:
        _LOGGER.error(error)
        return False

    name = config.get(CONF_NAME)

    sensors = []
    for variable in config[CONF_MONITORED_CONDITIONS]:
        sensors.append(DarkSkySensor(forecast_data, variable, name))

    add_devices(sensors)


# pylint: disable=too-few-public-methods
class DarkSkySensor(Entity):
    """Implementation of a Dark Sky sensor."""

    def __init__(self, forecast_data, sensor_type, name):
        """Initialize the sensor."""
        self.client_name = name
        self._name = SENSOR_TYPES[sensor_type][0]
        self.forecast_data = forecast_data
        self.type = sensor_type
        self._state = None
        self._unit_of_measurement = None

        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self.client_name, self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def unit_system(self):
        """Return the unit system of this entity."""
        return self.forecast_data.unit_system

    def update_unit_of_measurement(self):
        """Update units based on unit system."""
        unit_index = {
            'si': 1,
            'us': 2,
            'ca': 3,
            'uk': 4,
            'uk2': 5
        }.get(self.unit_system, 1)
        self._unit_of_measurement = SENSOR_TYPES[self.type][unit_index]

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return SENSOR_TYPES[self.type][6]

    # pylint: disable=too-many-branches,too-many-statements
    def update(self):
        """Get the latest data from Dark Sky and updates the states."""
        # Call the API for new forecast data. Each sensor will re-trigger this
        # same exact call, but that's fine. We cache results for a short period
        # of time to prevent hitting API limits. Note that Dark Sky will
        # charge users for too many calls in 1 day, so take care when updating.
        self.forecast_data.update()
        self.update_unit_of_measurement()

        if self.type == 'minutely_summary':
            self.forecast_data.update_minutely()
            minutely = self.forecast_data.data_minutely
            self._state = getattr(minutely, 'summary', '')
        elif self.type == 'hourly_summary':
            self.forecast_data.update_hourly()
            hourly = self.forecast_data.data_hourly
            self._state = getattr(hourly, 'summary', '')
        elif self.type in ['daily_summary',
                           'temperature_min',
                           'temperature_max',
                           'apparent_temperature_min',
                           'apparent_temperature_max',
                           'precip_intensity_max']:
            self.forecast_data.update_daily()
            daily = self.forecast_data.data_daily
            if self.type == 'daily_summary':
                self._state = getattr(daily, 'summary', '')
            else:
                if hasattr(daily, 'data'):
                    self._state = self.get_state(daily.data[0])
                else:
                    self._state = 0
        else:
            self.forecast_data.update_currently()
            currently = self.forecast_data.data_currently
            self._state = self.get_state(currently)

    def get_state(self, data):
        """
        Helper function that returns a new state based on the type.

        If the sensor type is unknown, the current state is returned.
        """
        lookup_type = convert_to_camel(self.type)
        state = getattr(data, lookup_type, 0)

        # Some state data needs to be rounded to whole values or converted to
        # percentages
        if self.type in ['precip_probability', 'cloud_cover', 'humidity']:
            return round(state * 100, 1)
        elif (self.type in ['dew_point', 'temperature', 'apparent_temperature',
                            'temperature_min', 'temperature_max',
                            'apparent_temperature_min',
                            'apparent_temperature_max',
                            'pressure', 'ozone']):
            return round(state, 1)
        return state


def convert_to_camel(data):
    """
    Convert snake case (foo_bar_bat) to camel case (fooBarBat).

    This is not pythonic, but needed for certain situations
    """
    components = data.split('_')
    return components[0] + "".join(x.title() for x in components[1:])


class DarkSkyData(object):
    """Get the latest data from Darksky."""

    # pylint: disable=too-many-instance-attributes
    def __init__(self, api_key, latitude, longitude, units, interval):
        """Initialize the data object."""
        self._api_key = api_key
        self.latitude = latitude
        self.longitude = longitude
        self.units = units

        self.data = None
        self.unit_system = None
        self.data_currently = None
        self.data_minutely = None
        self.data_hourly = None
        self.data_daily = None

        # Apply throttling to methods using configured interval
        self.update = Throttle(interval)(self._update)
        self.update_currently = Throttle(interval)(self._update_currently)
        self.update_minutely = Throttle(interval)(self._update_minutely)
        self.update_hourly = Throttle(interval)(self._update_hourly)
        self.update_daily = Throttle(interval)(self._update_daily)

        self.update()

    def _update(self):
        """Get the latest data from Dark Sky."""
        import forecastio

        try:
            self.data = forecastio.load_forecast(
                self._api_key, self.latitude, self.longitude, units=self.units)
        except (ConnectError, HTTPError, Timeout, ValueError) as error:
            raise ValueError("Unable to init Dark Sky. %s", error)
        self.unit_system = self.data.json['flags']['units']

    def _update_currently(self):
        """Update currently data."""
        self.data_currently = self.data.currently()

    def _update_minutely(self):
        """Update minutely data."""
        self.data_minutely = self.data.minutely()

    def _update_hourly(self):
        """Update hourly data."""
        self.data_hourly = self.data.hourly()

    def _update_daily(self):
        """Update daily data."""
        self.data_daily = self.data.daily()
