"""
Support for Met.no weather service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/weather.met/
"""
import asyncio
import logging
from datetime import timedelta

from random import randrange
from xml.parsers.expat import ExpatError

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.components.weather import PLATFORM_SCHEMA, WeatherEntity
from homeassistant.const import (CONF_ELEVATION, CONF_LATITUDE, CONF_LONGITUDE,
                                 CONF_NAME, TEMP_CELSIUS)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util, Throttle

REQUIREMENTS = ['xmltodict==0.11.0']

_LOGGER = logging.getLogger(__name__)

CONF_ATTRIBUTION = "Weather forecast from met.no, delivered " \
                   "by the Norwegian Meteorological Institute."
DEFAULT_NAME = "Met.no"

# https://api.met.no/weatherapi/weathericon/_/documentation/#___top
CONDITIONS = {1: 'sunny',
              2: 'partlycloudy',
              3: 'partlycloudy',
              4: 'cloudy',
              5: 'rainy',
              6: 'lightning-rainy',
              7: 'snowy-rainy',
              8: 'snowy',
              9: 'rainy',
              10: 'rainy',
              11: 'lightning-rainy',
              12: 'snowy-rainy',
              13: 'snowy',
              14: 'snowy',
              15: 'fog',
              20: 'lightning-rainy',
              21: 'lightning-rainy',
              22: 'lightning-rainy',
              23: 'lightning-rainy',
              24: 'lightning-rainy',
              25: 'lightning-rainy',
              26: 'lightning-rainy',
              27: 'lightning-rainy',
              28: 'lightning-rainy',
              29: 'lightning-rainy',
              30: 'lightning-rainy',
              31: 'lightning-rainy',
              32: 'lightning-rainy',
              33: 'lightning-rainy',
              34: 'lightning-rainy',
              40: 'rainy',
              41: 'rainy',
              42: 'snowy-rainy',
              43: 'snowy-rainy',
              44: 'snowy',
              45: 'snowy',
              46: 'rainy',
              47: 'snowy-rainy',
              48: 'snowy-rainy',
              49: 'snowy',
              50: 'snowy',
              }

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Inclusive(CONF_LATITUDE, 'coordinates',
                  'Latitude and longitude must exist together'): cv.latitude,
    vol.Inclusive(CONF_LONGITUDE, 'coordinates',
                  'Latitude and longitude must exist together'): cv.longitude,
})

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=10)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Met.no weather platform."""
    elevation = config.get(CONF_ELEVATION, hass.config.elevation or 0)
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    name = config.get(CONF_NAME)

    if None in (latitude, longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return

    coordinates = {
        'lat': str(latitude),
        'lon': str(longitude),
        'msl': str(elevation),
    }

    async_add_entities([MetWeather(name, coordinates)])


class MetWeather(WeatherEntity):
    """Implementation of a Met.no weather condition."""

    def __init__(self, name, coordinates):
        """Initialise the platform with a data instance and site."""
        self._name = name
        self._urlparams = coordinates
        self._weather_data = None
        self._url = 'https://aa015h6buqvih86i1.api.met.no/'\
            'weatherapi/locationforecast/1.9/'
        self._temperature = None
        self._condition = None
        self._pressure = None
        self._humidity = None
        self._wind_speed = None
        self._wind_bearing = None

    async def async_added_to_hass(self):
        """Start unavailability tracking."""
        await self._fetching_data()

    async def _fetching_data(self, *_):
        """Get the latest data from met.no."""
        import xmltodict

        def try_again(err: str):
            """Retry in 15 to 20 minutes."""
            minutes = 15 + randrange(6)
            _LOGGER.error("Retrying in %i minutes: %s", minutes, err)
            async_call_later(self.hass, minutes*60, self._fetching_data)
        try:
            websession = async_get_clientsession(self.hass)
            with async_timeout.timeout(10, loop=self.hass.loop):
                resp = await websession.get(
                    self._url, params=self._urlparams)
            if resp.status != 200:
                try_again('{} returned {}'.format(resp.url, resp.status))
                return
            text = await resp.text()

        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            try_again(err)
            return

        try:
            self._weather_data = xmltodict.parse(text)['weatherdata']
        except (ExpatError, IndexError) as err:
            try_again(err)
            return

        async_call_later(self.hass, 60*60, self._fetching_data)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from Met.no."""
        if self._weather_data is None:
            return

        now = dt_util.utcnow()

        ordered_entries = []
        for time_entry in self._weather_data['product']['time']:
            valid_from = dt_util.parse_datetime(time_entry['@from'])
            valid_to = dt_util.parse_datetime(time_entry['@to'])

            if now >= valid_to:
                # Has already passed. Never select this.
                continue

            average_dist = (abs((valid_to - now).total_seconds()) +
                            abs((valid_from - now).total_seconds()))

            ordered_entries.append((average_dist, time_entry))

        if not ordered_entries:
            return
        ordered_entries.sort(key=lambda item: item[0])

        self._temperature = get_forecast('temperature', ordered_entries)
        self._condition = CONDITIONS.get(get_forecast('symbol',
                                                      ordered_entries))
        self._pressure = get_forecast('pressure', ordered_entries)
        self._humidity = get_forecast('humidity', ordered_entries)
        self._wind_speed = get_forecast('windSpeed', ordered_entries)
        self._wind_bearing = get_forecast('windDirection', ordered_entries)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def condition(self):
        """Return the current condition."""
        return self._condition

    @property
    def temperature(self):
        """Return the temperature."""
        return self._temperature

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def pressure(self):
        """Return the pressure."""
        return self._pressure

    @property
    def humidity(self):
        """Return the humidity."""
        return self._humidity

    @property
    def wind_speed(self):
        """Return the wind speed."""
        return self._wind_speed

    @property
    def wind_bearing(self):
        """Return the wind direction."""
        return self._wind_bearing

    @property
    def attribution(self):
        """Return the attribution."""
        return CONF_ATTRIBUTION


def get_forecast(param, data):
    """Retrieve forecast parameter."""
    try:
        for (_, selected_time_entry) in data:
            loc_data = selected_time_entry['location']

            if param not in loc_data:
                continue

            if param == 'precipitation':
                new_state = loc_data[param]['@value']
            elif param == 'symbol':
                new_state = int(float(loc_data[param]['@number']))
            elif param in ('temperature', 'pressure', 'humidity',
                           'dewpointTemperature'):
                new_state = round(float(loc_data[param]['@value']), 1)
            elif param in ('windSpeed', 'windGust'):
                new_state = round(float(loc_data[param]['@mps']) * 3.6, 1)
            elif param == 'windDirection':
                new_state = round(float(loc_data[param]['@deg']), 1)
            elif param in ('fog', 'cloudiness', 'lowClouds',
                           'mediumClouds', 'highClouds'):
                new_state = round(float(loc_data[param]['@percent']), 1)
            return new_state
    except (ValueError, IndexError, KeyError):
        return None
