"""
Support for Met.no weather service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/weather.met/
"""
import logging
from random import randrange

import voluptuous as vol

from homeassistant.components.weather import PLATFORM_SCHEMA, WeatherEntity
from homeassistant.const import (CONF_ELEVATION, CONF_LATITUDE, CONF_LONGITUDE,
                                 CONF_NAME, TEMP_CELSIUS)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import (async_track_utc_time_change,
                                         async_call_later)
from homeassistant.util import dt as dt_util

REQUIREMENTS = ['pyMetno==0.2.0']

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

    async_add_entities([MetWeather(name, coordinates,
                                   async_get_clientsession(hass))])


class MetWeather(WeatherEntity):
    """Implementation of a Met.no weather condition."""

    def __init__(self, name, coordinates, clientsession):
        """Initialise the platform with a data instance and site."""
        import metno
        self._name = name
        self._weather_data = metno.MetWeatherData(coordinates,
                                                  clientsession,
                                                  URL
                                                  )
        self._temperature = None
        self._condition = None
        self._pressure = None
        self._humidity = None
        self._wind_speed = None
        self._wind_bearing = None

    async def async_added_to_hass(self):
        """Start fetching data."""
        await self._fetch_data()
        async_track_utc_time_change(self.hass, self._update,
                                    minute=31, second=0)

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
        import metno
        if self._weather_data is None:
            return

        now = dt_util.utcnow()

        ordered_entries = []
        for time_entry in self._weather_data.data['product']['time']:
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

        self._temperature = metno.get_forecast('temperature', ordered_entries)
        self._condition = CONDITIONS.get(metno.get_forecast('symbol',
                                                            ordered_entries))
        self._pressure = metno.get_forecast('pressure', ordered_entries)
        self._humidity = metno.get_forecast('humidity', ordered_entries)
        self._wind_speed = metno.get_forecast('windSpeed', ordered_entries)
        self._wind_bearing = metno.get_forecast('windDirection',
                                                ordered_entries)
        self.async_schedule_update_ha_state()

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
