"""Support for the Swedish weather institute weather service."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

import aiohttp
import async_timeout
from smhi import Smhi
from smhi.smhi_lib import SmhiForecastException

from homeassistant.components.weather import (
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_EXCEPTIONAL,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_HAIL,
    ATTR_CONDITION_LIGHTNING,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY,
    ATTR_CONDITION_WINDY_VARIANT,
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
    WeatherEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.util import Throttle, slugify

from .const import (
    ATTR_SMHI_CLOUDINESS,
    ATTR_SMHI_THUNDER_PROBABILITY,
    ATTR_SMHI_WIND_GUST_SPEED,
    ENTITY_ID_SENSOR_FORMAT,
)

_LOGGER = logging.getLogger(__name__)

# Used to map condition from API results
CONDITION_CLASSES = {
    ATTR_CONDITION_CLOUDY: [5, 6],
    ATTR_CONDITION_FOG: [7],
    ATTR_CONDITION_HAIL: [],
    ATTR_CONDITION_LIGHTNING: [21],
    ATTR_CONDITION_LIGHTNING_RAINY: [11],
    ATTR_CONDITION_PARTLYCLOUDY: [3, 4],
    ATTR_CONDITION_POURING: [10, 20],
    ATTR_CONDITION_RAINY: [8, 9, 18, 19],
    ATTR_CONDITION_SNOWY: [15, 16, 17, 25, 26, 27],
    ATTR_CONDITION_SNOWY_RAINY: [12, 13, 14, 22, 23, 24],
    ATTR_CONDITION_SUNNY: [1, 2],
    ATTR_CONDITION_WINDY: [],
    ATTR_CONDITION_WINDY_VARIANT: [],
    ATTR_CONDITION_EXCEPTIONAL: [],
}

# 5 minutes between retrying connect to API again
RETRY_TIMEOUT = 5 * 60

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=31)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, config_entries
) -> bool:
    """Add a weather entity from map location."""
    location = config_entry.data
    name = slugify(location[CONF_NAME])

    session = aiohttp_client.async_get_clientsession(hass)

    entity = SmhiWeather(
        location[CONF_NAME],
        location[CONF_LATITUDE],
        location[CONF_LONGITUDE],
        session=session,
    )
    entity.entity_id = ENTITY_ID_SENSOR_FORMAT.format(name)

    config_entries([entity], True)
    return True


class SmhiWeather(WeatherEntity):
    """Representation of a weather entity."""

    def __init__(
        self,
        name: str,
        latitude: str,
        longitude: str,
        session: aiohttp.ClientSession = None,
    ) -> None:
        """Initialize the SMHI weather entity."""

        self._name = name
        self._latitude = latitude
        self._longitude = longitude
        self._forecasts = None
        self._fail_count = 0
        self._smhi_api = Smhi(self._longitude, self._latitude, session=session)

    @property
    def unique_id(self) -> str:
        """Return a unique id."""
        return f"{self._latitude}, {self._longitude}"

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self) -> None:
        """Refresh the forecast data from SMHI weather API."""
        try:
            with async_timeout.timeout(10):
                self._forecasts = await self.get_weather_forecast()
                self._fail_count = 0

        except (asyncio.TimeoutError, SmhiForecastException):
            _LOGGER.error("Failed to connect to SMHI API, retry in 5 minutes")
            self._fail_count += 1
            if self._fail_count < 3:
                self.hass.helpers.event.async_call_later(
                    RETRY_TIMEOUT, self.retry_update
                )

    async def retry_update(self, _):
        """Retry refresh weather forecast."""
        await self.async_update()

    async def get_weather_forecast(self) -> []:
        """Return the current forecasts from SMHI API."""
        return await self._smhi_api.async_get_forecast()

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def temperature(self) -> int:
        """Return the temperature."""
        if self._forecasts is not None:
            return self._forecasts[0].temperature
        return None

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def humidity(self) -> int:
        """Return the humidity."""
        if self._forecasts is not None:
            return self._forecasts[0].humidity
        return None

    @property
    def wind_speed(self) -> float:
        """Return the wind speed."""
        if self._forecasts is not None:
            # Convert from m/s to km/h
            return round(self._forecasts[0].wind_speed * 18 / 5)
        return None

    @property
    def wind_gust_speed(self) -> float:
        """Return the wind gust speed."""
        if self._forecasts is not None:
            # Convert from m/s to km/h
            return round(self._forecasts[0].wind_gust * 18 / 5)
        return None

    @property
    def wind_bearing(self) -> int:
        """Return the wind bearing."""
        if self._forecasts is not None:
            return self._forecasts[0].wind_direction
        return None

    @property
    def visibility(self) -> float:
        """Return the visibility."""
        if self._forecasts is not None:
            return self._forecasts[0].horizontal_visibility
        return None

    @property
    def pressure(self) -> int:
        """Return the pressure."""
        if self._forecasts is not None:
            return self._forecasts[0].pressure
        return None

    @property
    def cloudiness(self) -> int:
        """Return the cloudiness."""
        if self._forecasts is not None:
            return self._forecasts[0].cloudiness
        return None

    @property
    def thunder_probability(self) -> int:
        """Return the chance of thunder, unit Percent."""
        if self._forecasts is not None:
            return self._forecasts[0].thunder
        return None

    @property
    def condition(self) -> str:
        """Return the weather condition."""
        if self._forecasts is None:
            return None
        return next(
            (k for k, v in CONDITION_CLASSES.items() if self._forecasts[0].symbol in v),
            None,
        )

    @property
    def attribution(self) -> str:
        """Return the attribution."""
        return "Swedish weather institute (SMHI)"

    @property
    def forecast(self) -> list:
        """Return the forecast."""
        if self._forecasts is None or len(self._forecasts) < 2:
            return None

        data = []

        for forecast in self._forecasts[1:]:
            condition = next(
                (k for k, v in CONDITION_CLASSES.items() if forecast.symbol in v), None
            )

            data.append(
                {
                    ATTR_FORECAST_TIME: forecast.valid_time.isoformat(),
                    ATTR_FORECAST_TEMP: forecast.temperature_max,
                    ATTR_FORECAST_TEMP_LOW: forecast.temperature_min,
                    ATTR_FORECAST_PRECIPITATION: round(forecast.total_precipitation, 1),
                    ATTR_FORECAST_CONDITION: condition,
                }
            )

        return data

    @property
    def extra_state_attributes(self) -> dict:
        """Return SMHI specific attributes."""
        extra_attributes = {}
        if self.cloudiness is not None:
            extra_attributes[ATTR_SMHI_CLOUDINESS] = self.cloudiness
        if self.wind_gust_speed is not None:
            extra_attributes[ATTR_SMHI_WIND_GUST_SPEED] = self.wind_gust_speed
        if self.thunder_probability is not None:
            extra_attributes[ATTR_SMHI_THUNDER_PROBABILITY] = self.thunder_probability
        return extra_attributes
