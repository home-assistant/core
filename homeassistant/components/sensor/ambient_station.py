"""
Support for Ambient Weather Station Service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.ambient_station/
"""

import asyncio
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_API_KEY, CONF_MONITORED_CONDITIONS
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['ambient_api==1.5.2']

CONF_APP_KEY = 'app_key'

SENSOR_NAME = 0
SENSOR_UNITS = 1

CONF_UNITS = 'units'
UNITS_US = 'us'
UNITS_SI = 'si'
UNIT_SYSTEM = {UNITS_US: 0, UNITS_SI: 1}

SCAN_INTERVAL = timedelta(seconds=300)

SENSOR_TYPES = {
    'winddir': ['Wind Dir', 'º'],
    'windspeedmph': ['Wind Speed', 'mph'],
    'windgustmph': ['Wind Gust', 'mph'],
    'maxdailygust': ['Max Gust', 'mph'],
    'windgustdir': ['Gust Dir', 'º'],
    'windspdmph_avg2m': ['Wind Avg 2m', 'mph'],
    'winddir_avg2m': ['Wind Dir Avg 2m', 'mph'],
    'windspdmph_avg10m': ['Wind Avg 10m', 'mph'],
    'winddir_avg10m': ['Wind Dir Avg 10m', 'º'],
    'humidity': ['Humidity', '%'],
    'humidityin': ['Humidity In', '%'],
    'tempf': ['Temp', ['ºF', 'ºC']],
    'tempinf': ['Inside Temp', ['ºF', 'ºC']],
    'battout': ['Battery', ''],
    'hourlyrainin': ['Hourly Rain Rate', 'in/hr'],
    'dailyrainin': ['Daily Rain', 'in'],
    '24hourrainin': ['24 Hr Rain', 'in'],
    'weeklyrainin': ['Weekly Rain', 'in'],
    'monthlyrainin': ['Monthly Rain', 'in'],
    'yearlyrainin': ['Yearly Rain', 'in'],
    'eventrainin': ['Event Rain', 'in'],
    'totalrainin': ['Lifetime Rain', 'in'],
    'baromrelin': ['Rel Pressure', 'inHg'],
    'baromabsin': ['Abs Pressure', 'inHg'],
    'uv': ['uv', 'Index'],
    'solarradiation': ['Solar Rad', 'W/m^2'],
    'co2': ['co2', 'ppm'],
    'lastRain': ['Last Rain', ''],
    'dewPoint': ['Dew Point', ['ºF', 'ºC']],
    'feelsLike': ['Feels Like', ['ºF', 'ºC']],
}

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_APP_KEY): cv.string,
    vol.Required(CONF_MONITORED_CONDITIONS):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Optional(CONF_UNITS): vol.In([UNITS_SI, UNITS_US]),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Initialze each sensor platform for each monitored condition."""
    api_key = config[CONF_API_KEY]
    app_key = config[CONF_APP_KEY]
    station_data = AmbientStationData(hass, api_key, app_key)
    if not station_data.connect_success:
        _LOGGER.error("Could not connect to weather station API")
        return

    sensor_list = []

    if CONF_UNITS in config:
        sys_units = config[CONF_UNITS]
    elif hass.config.units.is_metric:
        sys_units = UNITS_SI
    else:
        sys_units = UNITS_US

    for condition in config[CONF_MONITORED_CONDITIONS]:
        # create a sensor object for each monitored condition
        sensor_params = SENSOR_TYPES[condition]
        name = sensor_params[SENSOR_NAME]
        units = sensor_params[SENSOR_UNITS]
        if isinstance(units, list):
            units = sensor_params[SENSOR_UNITS][UNIT_SYSTEM[sys_units]]

        sensor_list.append(AmbientWeatherSensor(station_data, condition,
                                                name, units))

    add_entities(sensor_list)


class AmbientWeatherSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, station_data, condition, name, units):
        """Initialize the sensor."""
        self._state = None
        self.station_data = station_data
        self._condition = condition
        self._name = name
        self._units = units

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._units

    async def async_update(self):
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        _LOGGER.debug("Getting data for sensor: %s", self._name)
        data = await self.station_data.get_data()
        if data is None:
            # update likely got throttled and returned None, so use the cached
            # data from the station_data object
            self._state = self.station_data.data[self._condition]
        else:
            if self._condition in data:
                self._state = data[self._condition]
            else:
                _LOGGER.warning("%s sensor data not available from the "
                                "station", self._condition)

        _LOGGER.debug("Sensor: %s | Data: %s", self._name, self._state)


class AmbientStationData:
    """Class to interface with ambient-api library."""

    def __init__(self, hass, api_key, app_key):
        """Initialize station data object."""
        self.hass = hass
        self._api_keys = {
            'AMBIENT_ENDPOINT':
            'https://api.ambientweather.net/v1',
            'AMBIENT_API_KEY': api_key,
            'AMBIENT_APPLICATION_KEY': app_key,
            'log_level': 'DEBUG'
        }

        self.data = None
        self._station = None
        self._api = None
        self._devices = None
        self.connect_success = False

        self.get_data = Throttle(SCAN_INTERVAL)(self.async_update)
        self._connect_api()     # attempt to connect to API

    async def async_update(self):
        """Get new data."""
        # refresh API connection since servers turn over nightly
        _LOGGER.debug("Getting new data from server")
        new_data = None
        await self.hass.async_add_executor_job(self._connect_api)
        await asyncio.sleep(2)   # need minimum 2 seconds between API calls
        if self._station is not None:
            data = await self.hass.async_add_executor_job(
                self._station.get_data)
            if data is not None:
                new_data = data[0]
                self.data = new_data
            else:
                _LOGGER.debug("data is None type")
        else:
            _LOGGER.debug("Station is None type")

        return new_data

    def _connect_api(self):
        """Connect to the API and capture new data."""
        from ambient_api.ambientapi import AmbientAPI

        self._api = AmbientAPI(**self._api_keys)
        self._devices = self._api.get_devices()

        if self._devices:
            self._station = self._devices[0]
            if self._station is not None:
                self.connect_success = True
        else:
            _LOGGER.debug("No station devices available")
