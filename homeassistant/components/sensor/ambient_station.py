"""
Support for Ambient Weather Station Service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.ambient_station/
"""
import asyncio
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_API_KEY, CONF_MONITORED_CONDITIONS
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['ambient_api==1.5.2']

_LOGGER = logging.getLogger(__name__)

CONF_APP_KEY = 'app_key'
CONF_UNITS = 'units'

SENSOR_NAME = 0
SENSOR_UNITS = 1

UNITS_US = 'us'
UNITS_SI = 'si'
UNIT_SYSTEM = {UNITS_US: 0, UNITS_SI: 1}

DEFAULT_SCAN_INTERVAL = timedelta(minutes=5)

SENSOR_TYPES = {
    '24hourrainin': ['24 Hr Rain', 'in'],
    'baromabsin': ['Abs Pressure', 'inHg'],
    'baromrelin': ['Rel Pressure', 'inHg'],
    'battout': ['Battery', ''],
    'co2': ['co2', 'ppm'],
    'dailyrainin': ['Daily Rain', 'in'],
    'dewPoint': ['Dew Point', ['°F', '°C']],
    'eventrainin': ['Event Rain', 'in'],
    'feelsLike': ['Feels Like', ['°F', '°C']],
    'hourlyrainin': ['Hourly Rain Rate', 'in/hr'],
    'humidity': ['Humidity', '%'],
    'humidityin': ['Humidity In', '%'],
    'lastRain': ['Last Rain', ''],
    'maxdailygust': ['Max Gust', 'mph'],
    'monthlyrainin': ['Monthly Rain', 'in'],
    'solarradiation': ['Solar Rad', 'W/m^2'],
    'tempf': ['Temp', ['°F', '°C']],
    'tempinf': ['Inside Temp', ['°F', '°C']],
    'totalrainin': ['Lifetime Rain', 'in'],
    'uv': ['uv', 'Index'],
    'weeklyrainin': ['Weekly Rain', 'in'],
    'winddir': ['Wind Dir', '°'],
    'winddir_avg10m': ['Wind Dir Avg 10m', '°'],
    'winddir_avg2m': ['Wind Dir Avg 2m', 'mph'],
    'windgustdir': ['Gust Dir', '°'],
    'windgustmph': ['Wind Gust', 'mph'],
    'windspdmph_avg10m': ['Wind Avg 10m', 'mph'],
    'windspdmph_avg2m': ['Wind Avg 2m', 'mph'],
    'windspeedmph': ['Wind Speed', 'mph'],
    'yearlyrainin': ['Yearly Rain', 'in'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_APP_KEY): cv.string,
    vol.Required(CONF_API_KEY): cv.string,
    vol.Optional(CONF_MONITORED_CONDITIONS, default=list(SENSOR_TYPES)):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Optional(CONF_UNITS): vol.In([UNITS_SI, UNITS_US]),
})


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Initialze each sensor platform for each monitored condition."""
    from ambient_api.ambientapi import AmbientAPI

    if CONF_UNITS in config:
        sys_units = config[CONF_UNITS]
    elif hass.config.units.is_metric:
        sys_units = UNITS_SI
    else:
        sys_units = UNITS_US

    api = AmbientAPI(
        AMBIENT_API_KEY=config[CONF_API_KEY],
        AMBIENT_APPLICATION_KEY=config[CONF_APP_KEY],
        log_level='DEBUG')

    data = AmbientStationData(hass, api)
    await data.async_update()

    sensor_list = []
    for station in data.stations:
        for condition in config[CONF_MONITORED_CONDITIONS]:
            sensor_params = SENSOR_TYPES[condition]
            name = sensor_params[SENSOR_NAME]
            units = sensor_params[SENSOR_UNITS]
            if isinstance(units, list):
                units = sensor_params[SENSOR_UNITS][UNIT_SYSTEM[sys_units]]

            sensor_list.append(
                AmbientWeatherSensor(
                    data, station, condition, name, units))

    async_add_entities(sensor_list, True)


class AmbientWeatherSensor(Entity):
    """Define an Ambient sensor."""

    def __init__(self, data, station, condition, name, units):
        """Initialize the sensor."""
        self._condition = condition
        self._data = data
        self._name = name
        self._state = None
        self._station = station
        self._units = units

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{0}_{1}'.format(self._station.info['name'], self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._units

    @property
    def unique_id(self):
        """Return a unique, unchanging string that represents this sensor."""
        return '{0}_{1}'.format(self._station.mac_address, self._name)

    async def async_update(self):
        """Fetch new state data for the sensor."""
        await self._data.async_update()
        latest_data = self._data.data[self._station.mac_address]

        try:
            self._state = latest_data[self._condition]
        except KeyError:
            _LOGGER.warning('No data for condition: %s', self._condition)


class AmbientStationData:
    """Define an object to retrieve data from the Ambient API."""

    def __init__(self, hass, api):
        """Initialize the station data object."""
        self._api = api
        self._hass = hass
        self.data = {}
        self.stations = []

    @Throttle(DEFAULT_SCAN_INTERVAL)
    async def async_update(self):
        """Get new data for all stations."""
        # Ambient's API has really aggressive rate limiting (no more than 1
        # request per second), so throughout this method, we make sure to sleep
        # at least 1 second before firing further requests:
        self.stations = await self._hass.async_add_executor_job(
            self._api.get_devices)
        await asyncio.sleep(1)

        for idx, station in enumerate(self.stations):
            if idx > 0:
                await asyncio.sleep(1)

            data = await self._hass.async_add_executor_job(station.get_data)
            _LOGGER.debug(
                'New data for station "%s": %s', station.info['name'], data)

            self.data[station.mac_address] = data[0]
