"""Support for IPMA weather service."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Literal

from pyipma.api import IPMA_API
from pyipma.forecast import Forecast as IPMAForecast
from pyipma.location import Location

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_NATIVE_TEMP,
    ATTR_FORECAST_NATIVE_TEMP_LOW,
    ATTR_FORECAST_NATIVE_WIND_SPEED,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    Forecast,
    WeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_MODE,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.sun import is_up
from homeassistant.util import Throttle

from .const import (
    ATTRIBUTION,
    CONDITION_MAP,
    DATA_API,
    DATA_LOCATION,
    DOMAIN,
    MIN_TIME_BETWEEN_UPDATES,
)
from .entity import IPMADevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add a weather entity from a config_entry."""
    api = hass.data[DOMAIN][config_entry.entry_id][DATA_API]
    location = hass.data[DOMAIN][config_entry.entry_id][DATA_LOCATION]
    async_add_entities([IPMAWeather(api, location, config_entry)], True)


class IPMAWeather(WeatherEntity, IPMADevice):
    """Representation of a weather condition."""

    _attr_attribution = ATTRIBUTION
    _attr_name = None
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_DAILY | WeatherEntityFeature.FORECAST_HOURLY
    )

    def __init__(
        self, api: IPMA_API, location: Location, config_entry: ConfigEntry
    ) -> None:
        """Initialise the platform with a data instance and station name."""
        IPMADevice.__init__(self, api, location)
        self._mode = config_entry.data.get(CONF_MODE)
        self._period = 1 if config_entry.data.get(CONF_MODE) == "hourly" else 24
        self._observation = None
        self._daily_forecast: list[IPMAForecast] | None = None
        self._hourly_forecast: list[IPMAForecast] | None = None
        if self._mode is not None:
            self._attr_unique_id = f"{self._location.station_latitude}, {self._location.station_longitude}, {self._mode}"
        else:
            self._attr_unique_id = (
                f"{self._location.station_latitude}, {self._location.station_longitude}"
            )

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self) -> None:
        """Update Condition and Forecast."""
        async with asyncio.timeout(10):
            new_observation = await self._location.observation(self._api)

            if new_observation:
                self._observation = new_observation
            else:
                _LOGGER.warning("Could not update weather observation")

            if self._period == 24 or self._forecast_listeners["daily"]:
                await self._update_forecast("daily", 24, True)
            else:
                self._daily_forecast = None

            await self._update_forecast("hourly", 1, True)

            _LOGGER.debug(
                "Updated location %s based on %s, current observation %s",
                self._location.name,
                self._location.station,
                self._observation,
            )

    async def _update_forecast(
        self,
        forecast_type: Literal["daily", "hourly"],
        period: int,
        update_listeners: bool,
    ) -> None:
        """Update weather forecast."""
        new_forecast = await self._location.forecast(self._api, period)
        if new_forecast:
            setattr(self, f"_{forecast_type}_forecast", new_forecast)
            if update_listeners:
                await self.async_update_listeners((forecast_type,))
        else:
            _LOGGER.warning("Could not update %s weather forecast", forecast_type)

    def _condition_conversion(self, identifier, forecast_dt):
        """Convert from IPMA weather_type id to HA."""
        if identifier == 1 and not is_up(self.hass, forecast_dt):
            identifier = -identifier

        return CONDITION_MAP.get(identifier)

    @property
    def condition(self):
        """Return the current condition which is only available on the hourly forecast data."""
        forecast = self._hourly_forecast

        if not forecast:
            return None

        return self._condition_conversion(forecast[0].weather_type.id, None)

    @property
    def native_temperature(self):
        """Return the current temperature."""
        if not self._observation:
            return None

        return self._observation.temperature

    @property
    def native_pressure(self):
        """Return the current pressure."""
        if not self._observation:
            return None

        return self._observation.pressure

    @property
    def humidity(self):
        """Return the name of the sensor."""
        if not self._observation:
            return None

        return self._observation.humidity

    @property
    def native_wind_speed(self):
        """Return the current windspeed."""
        if not self._observation:
            return None

        return self._observation.wind_intensity_km

    @property
    def wind_bearing(self):
        """Return the current wind bearing (degrees)."""
        if not self._observation:
            return None

        return self._observation.wind_direction

    def _forecast(self, forecast: list[IPMAForecast] | None) -> list[Forecast]:
        """Return the forecast array."""
        if not forecast:
            return []

        return [
            {
                ATTR_FORECAST_TIME: data_in.forecast_date,
                ATTR_FORECAST_CONDITION: self._condition_conversion(
                    data_in.weather_type.id, data_in.forecast_date
                ),
                ATTR_FORECAST_NATIVE_TEMP_LOW: data_in.min_temperature,
                ATTR_FORECAST_NATIVE_TEMP: data_in.max_temperature,
                ATTR_FORECAST_PRECIPITATION_PROBABILITY: data_in.precipitation_probability,
                ATTR_FORECAST_NATIVE_WIND_SPEED: data_in.wind_strength,
                ATTR_FORECAST_WIND_BEARING: data_in.wind_direction,
            }
            for data_in in forecast
        ]

    async def _try_update_forecast(
        self,
        forecast_type: Literal["daily", "hourly"],
        period: int,
    ) -> None:
        """Try to update weather forecast."""
        with contextlib.suppress(TimeoutError):
            async with asyncio.timeout(10):
                await self._update_forecast(forecast_type, period, False)

    async def async_forecast_daily(self) -> list[Forecast]:
        """Return the daily forecast in native units."""
        await self._try_update_forecast("daily", 24)
        return self._forecast(self._daily_forecast)

    async def async_forecast_hourly(self) -> list[Forecast]:
        """Return the hourly forecast in native units."""
        await self._try_update_forecast("hourly", 1)
        return self._forecast(self._hourly_forecast)
