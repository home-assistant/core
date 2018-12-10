"""
Support for Yandex Weather.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/weather.yandex/
"""
import logging
from datetime import datetime, timedelta
from contextlib import wraps

import async_timeout
import voluptuous as vol

from homeassistant.components.weather import (
    WeatherEntity, PLATFORM_SCHEMA, ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION, ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW, ATTR_FORECAST_TIME)
from homeassistant.const import \
    CONF_NAME, TEMP_CELSIUS, CONF_LATITUDE, CONF_LONGITUDE, CONF_API_KEY
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import config_validation as cv

from homeassistant.util import Throttle

REQUIREMENTS = ['yandex-weather-api==0.2.3']

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = 'Яндекс.Погода'

# API limit is 50 req/day
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=40)

CONDITION_TO_HA = {
    "clear": "clear-night",
    "partly-cloudy": "partlycloudy",
    "cloudy": "cloudy",
    "overcast": "cloudy",
    "partly-cloudy-and-light-rain": "rainy",
    "partly-cloudy-and-rain": "pouring",
    "overcast-and-rain": "rainy",
    "overcast-thunderstorms-with-rain": "lightning-rainy",
    "cloudy-and-light-rain": "rainy",
    "overcast-and-light-rain": "rainy",
    "cloudy-and-rain": "rainy",
    "overcast-and-wet-snow": "snowy-rainy",
    "partly-cloudy-and-light-snow": "snowy",
    "partly-cloudy-and-snow": "snowy",
    "overcast-and-snow": "snowy",
    "cloudy-and-light-snow": "snowy",
    "overcast-and-light-snow": "snowy",
    "cloudy-and-snow": "snowy"
}

DAYPARTS_TIMEDELTA = (
    ("night", timedelta(hours=0)),
    ("morning", timedelta(hours=6)),
    ("day", timedelta(hours=12)),
    ("evening", timedelta(hours=18))
)


CONF_RATE = "rate"
CONF_UPDATE_TIMEOUT = "update_timeout"
RATE_INFORMERS = "informers"
RATE_FORECAST = "forecast"
VALID_RATES = (RATE_INFORMERS, RATE_FORECAST)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Optional(CONF_RATE): vol.Any(*VALID_RATES),
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_LATITUDE): cv.latitude,
    vol.Optional(CONF_LONGITUDE): cv.longitude,
    vol.Optional(CONF_UPDATE_TIMEOUT): cv.positive_timedelta
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the yandex weather platform."""
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    if None in (latitude, longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return
    latitude = float(latitude)
    longitude = float(longitude)
    websession = async_get_clientsession(hass)

    _LOGGER.debug("Initializing for coordinates %s, %s", latitude, longitude)

    async_add_entities([YandexWeather(
        websession, latitude, longitude, config)], True)


def not_none(prop):
    """A decorator for a class method to use a non-None value."""
    def __inner(func):
        @wraps(func)
        def decore(self, *args, **kwargs):
            if getattr(self, prop) is not None:
                return func(self, *args, **kwargs)
        return decore
    return __inner


class YandexWeather(WeatherEntity):
    """Representation of a weather condition."""

    def __init__(self, session, lat, lon, config):
        """Initialise the platform with a data instance and station name."""
        self._station_name = config.get(CONF_NAME)
        if self._station_name is None:
            self._station_name = "Weather at {}, {}".format(lat, lon)
        self._api_key = config.get(CONF_API_KEY)
        self._rate = config.get(CONF_RATE, "informers")
        update_timeout = config.get(
            CONF_UPDATE_TIMEOUT, MIN_TIME_BETWEEN_UPDATES)
        if update_timeout < MIN_TIME_BETWEEN_UPDATES \
                and self._rate == "informers":
            _LOGGER.error(
                "Update timeout is set too frequently for current rate. "
                "Rounding it to MIN_TIME_BETWEEN_UPDATES (00:40:00)")
            update_timeout = MIN_TIME_BETWEEN_UPDATES
        throttle_update = Throttle(update_timeout)
        self.async_update = throttle_update(self.async_update)
        self._lat = lat
        self._lon = lon
        self._session = session
        self._forecast = None
        from yandex_weather_api import async_get
        self._async_get = async_get

    # pylint: disable=method-hidden
    # because we need to throttle update function from configuration
    async def async_update(self):
        """Update Condition and Forecast."""
        with async_timeout.timeout(10, loop=self.hass.loop):
            _LOGGER.debug("Updating station %s",
                          self._station_name)
            self._forecast = await self._async_get(
                self._session, self._api_key,
                rate=self._rate, lat=self._lat, lon=self._lon
            )

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def name(self):
        """Return the name of the station."""
        return self._station_name

    @property
    @not_none("_forecast")
    def condition(self):
        """Return the current condition."""
        return CONDITION_TO_HA[self._forecast.fact.condition]

    @property
    @not_none("_forecast")
    def temperature(self):
        """Return the current temperature."""
        return self._forecast.fact.temp

    @property
    @not_none("_forecast")
    def pressure(self):
        """Return the current pressure."""
        return self._forecast.fact.pressure_mm

    @property
    @not_none("_forecast")
    def humidity(self):
        """Return the name of the sensor."""
        return self._forecast.fact.humidity

    @property
    @not_none("_forecast")
    def wind_speed(self):
        """Return the current windspeed."""
        return self._forecast.fact.wind_speed

    @property
    @not_none("_forecast")
    def wind_bearing(self):
        """Return the current wind bearing (degrees)."""
        return self._forecast.fact.wind_dir

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    @not_none("_forecast")
    def forecast(self):
        """Return the forecast array."""
        fcdata_out = []
        for data_in in self._forecast.forecast:
            date = datetime.strptime(data_in.date, "%Y-%m-%d")
            for part_name, part_dt in DAYPARTS_TIMEDELTA:
                data_out = {}
                data_out[ATTR_FORECAST_TIME] = date + part_dt
                part = data_in.parts.get(part_name)
                if part is None:
                    continue
                data_out[ATTR_FORECAST_CONDITION] =\
                    CONDITION_TO_HA[part.condition]
                data_out[ATTR_FORECAST_TEMP_LOW] = part.temp_min
                data_out[ATTR_FORECAST_TEMP] = part.temp_min
                data_out[ATTR_FORECAST_PRECIPITATION] = part.prec_prob
                fcdata_out.append(data_out)
        return fcdata_out
