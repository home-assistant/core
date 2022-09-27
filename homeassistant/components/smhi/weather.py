"""Support for the Swedish weather institute weather service."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import datetime, timedelta
import logging
from typing import Any, Final

import aiohttp
import async_timeout
from smhi import Smhi
from smhi.smhi_lib import SmhiForecast, SmhiForecastException

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
    ATTR_FORECAST_NATIVE_PRECIPITATION,
    ATTR_FORECAST_NATIVE_PRESSURE,
    ATTR_FORECAST_NATIVE_TEMP,
    ATTR_FORECAST_NATIVE_TEMP_LOW,
    ATTR_FORECAST_NATIVE_WIND_SPEED,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    ROUNDING_PRECISION,
    Forecast,
    WeatherEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_NAME,
    LENGTH_KILOMETERS,
    LENGTH_MILLIMETERS,
    PRESSURE_HPA,
    SPEED_METERS_PER_SECOND,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later
from homeassistant.util import Throttle, slugify
from homeassistant.util.unit_conversion import SpeedConverter

from .const import (
    ATTR_SMHI_CLOUDINESS,
    ATTR_SMHI_THUNDER_PROBABILITY,
    ATTR_SMHI_WIND_GUST_SPEED,
    DOMAIN,
    ENTITY_ID_SENSOR_FORMAT,
)

_LOGGER = logging.getLogger(__name__)

# Used to map condition from API results
CONDITION_CLASSES: Final[dict[str, list[int]]] = {
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

TIMEOUT = 10
# 5 minutes between retrying connect to API again
RETRY_TIMEOUT = 5 * 60

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=31)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add a weather entity from map location."""
    location = config_entry.data
    name = slugify(location[CONF_NAME])

    session = aiohttp_client.async_get_clientsession(hass)

    entity = SmhiWeather(
        location[CONF_NAME],
        location[CONF_LOCATION][CONF_LATITUDE],
        location[CONF_LOCATION][CONF_LONGITUDE],
        session=session,
    )
    entity.entity_id = ENTITY_ID_SENSOR_FORMAT.format(name)

    async_add_entities([entity], True)


class SmhiWeather(WeatherEntity):
    """Representation of a weather entity."""

    _attr_attribution = "Swedish weather institute (SMHI)"
    _attr_native_temperature_unit = TEMP_CELSIUS
    _attr_native_visibility_unit = LENGTH_KILOMETERS
    _attr_native_precipitation_unit = LENGTH_MILLIMETERS
    _attr_native_wind_speed_unit = SPEED_METERS_PER_SECOND
    _attr_native_pressure_unit = PRESSURE_HPA

    _attr_has_entity_name = True

    def __init__(
        self,
        name: str,
        latitude: str,
        longitude: str,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize the SMHI weather entity."""
        self._attr_unique_id = f"{latitude}, {longitude}"
        self._forecasts: list[SmhiForecast] | None = None
        self._fail_count = 0
        self._smhi_api = Smhi(longitude, latitude, session=session)
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, f"{latitude}, {longitude}")},
            manufacturer="SMHI",
            model="v2",
            name=name,
            configuration_url="http://opendata.smhi.se/apidocs/metfcst/parameters.html",
        )
        self._attr_condition = None
        self._attr_native_temperature = None

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return additional attributes."""
        if self._forecasts:
            wind_gust = SpeedConverter.convert(
                self._forecasts[0].wind_gust,
                SPEED_METERS_PER_SECOND,
                self._wind_speed_unit,
            )
            return {
                ATTR_SMHI_CLOUDINESS: self._forecasts[0].cloudiness,
                ATTR_SMHI_WIND_GUST_SPEED: round(wind_gust, ROUNDING_PRECISION),
                ATTR_SMHI_THUNDER_PROBABILITY: self._forecasts[0].thunder,
            }
        return None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self) -> None:
        """Refresh the forecast data from SMHI weather API."""
        try:
            async with async_timeout.timeout(TIMEOUT):
                self._forecasts = await self._smhi_api.async_get_forecast()
                self._fail_count = 0
        except (asyncio.TimeoutError, SmhiForecastException):
            _LOGGER.error("Failed to connect to SMHI API, retry in 5 minutes")
            self._fail_count += 1
            if self._fail_count < 3:
                async_call_later(self.hass, RETRY_TIMEOUT, self.retry_update)
                return

        if self._forecasts:
            self._attr_native_temperature = self._forecasts[0].temperature
            self._attr_humidity = self._forecasts[0].humidity
            self._attr_native_wind_speed = self._forecasts[0].wind_speed
            self._attr_wind_bearing = self._forecasts[0].wind_direction
            self._attr_native_visibility = self._forecasts[0].horizontal_visibility
            self._attr_native_pressure = self._forecasts[0].pressure
            self._attr_condition = next(
                (
                    k
                    for k, v in CONDITION_CLASSES.items()
                    if self._forecasts[0].symbol in v
                ),
                None,
            )

    async def retry_update(self, _: datetime) -> None:
        """Retry refresh weather forecast."""
        await self.async_update(  # pylint: disable=unexpected-keyword-arg
            no_throttle=True
        )

    @property
    def forecast(self) -> list[Forecast] | None:
        """Return the forecast."""
        if self._forecasts is None or len(self._forecasts) < 2:
            return None

        data: list[Forecast] = []

        for forecast in self._forecasts[1:]:
            condition = next(
                (k for k, v in CONDITION_CLASSES.items() if forecast.symbol in v), None
            )

            data.append(
                {
                    ATTR_FORECAST_TIME: forecast.valid_time.isoformat(),
                    ATTR_FORECAST_NATIVE_TEMP: forecast.temperature_max,
                    ATTR_FORECAST_NATIVE_TEMP_LOW: forecast.temperature_min,
                    ATTR_FORECAST_NATIVE_PRECIPITATION: forecast.total_precipitation,
                    ATTR_FORECAST_CONDITION: condition,
                    ATTR_FORECAST_NATIVE_PRESSURE: forecast.pressure,
                    ATTR_FORECAST_WIND_BEARING: forecast.wind_direction,
                    ATTR_FORECAST_NATIVE_WIND_SPEED: forecast.wind_speed,
                }
            )

        return data
