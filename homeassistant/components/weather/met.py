"""Support for Met.no weather service."""
import logging
from random import randrange

import voluptuous as vol

from homeassistant.components.weather import PLATFORM_SCHEMA, WeatherEntity
from homeassistant.const import (
    CONF_ELEVATION, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME, TEMP_CELSIUS)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import (
    async_call_later, async_track_utc_time_change)
import homeassistant.util.dt as dt_util

REQUIREMENTS = ['pyMetno==0.4.6']

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Weather forecast from met.no, delivered by the Norwegian " \
              "Meteorological Institute."
DEFAULT_NAME = "Met.no"

URL = 'https://aa015h6buqvih86i1.api.met.no/weatherapi/locationforecast/1.9/'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Inclusive(CONF_LATITUDE, 'coordinates',
                  'Latitude and longitude must exist together'): cv.latitude,
    vol.Inclusive(CONF_LONGITUDE, 'coordinates',
                  'Latitude and longitude must exist together'): cv.longitude,
})


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

    async_add_entities([MetWeather(
        name, coordinates, async_get_clientsession(hass))])


class MetWeather(WeatherEntity):
    """Implementation of a Met.no weather condition."""

    def __init__(self, name, coordinates, clientsession):
        """Initialise the platform with a data instance and site."""
        import metno
        self._name = name
        self._weather_data = metno.MetWeatherData(
            coordinates, clientsession, URL)
        self._current_weather_data = {}
        self._forecast_data = None

    async def async_added_to_hass(self):
        """Start fetching data."""
        await self._fetch_data()
        async_track_utc_time_change(
            self.hass, self._update, minute=31, second=0)

    async def _fetch_data(self, *_):
        """Get the latest data from met.no."""
        if not await self._weather_data.fetching_data():
            # Retry in 15 to 20 minutes.
            minutes = 15 + randrange(6)
            _LOGGER.error("Retrying in %i minutes", minutes)
            async_call_later(self.hass, minutes*60, self._fetch_data)
            return

        async_call_later(self.hass, 60*60, self._fetch_data)
        await self._update()

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    async def _update(self, *_):
        """Get the latest data from Met.no."""
        self._current_weather_data = self._weather_data.get_current_weather()
        time_zone = dt_util.DEFAULT_TIME_ZONE
        self._forecast_data = self._weather_data.get_forecast(time_zone)
        self.async_schedule_update_ha_state()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def condition(self):
        """Return the current condition."""
        return self._current_weather_data.get('condition')

    @property
    def temperature(self):
        """Return the temperature."""
        return self._current_weather_data.get('temperature')

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def pressure(self):
        """Return the pressure."""
        return self._current_weather_data.get('pressure')

    @property
    def humidity(self):
        """Return the humidity."""
        return self._current_weather_data.get('humidity')

    @property
    def wind_speed(self):
        """Return the wind speed."""
        return self._current_weather_data.get('wind_speed')

    @property
    def wind_bearing(self):
        """Return the wind direction."""
        return self._current_weather_data.get('wind_bearing')

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def forecast(self):
        """Return the forecast array."""
        return self._forecast_data
