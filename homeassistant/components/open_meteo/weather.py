"""Support for Open-Meteo weather."""

from __future__ import annotations

from datetime import datetime, time

from open_meteo import Forecast as OpenMeteoForecast

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_NATIVE_PRECIPITATION,
    ATTR_FORECAST_NATIVE_TEMP,
    ATTR_FORECAST_NATIVE_TEMP_LOW,
    ATTR_FORECAST_NATIVE_WIND_SPEED,
    ATTR_FORECAST_WIND_BEARING,
    Forecast,
    SingleCoordinatorWeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.const import UnitOfPrecipitationDepth, UnitOfSpeed, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import DOMAIN, WMO_TO_HA_CONDITION_MAP
from .coordinator import OpenMeteoConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenMeteoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Open-Meteo weather entity based on a config entry."""
    coordinator = entry.runtime_data
    async_add_entities([OpenMeteoWeatherEntity(entry=entry, coordinator=coordinator)])


class OpenMeteoWeatherEntity(
    SingleCoordinatorWeatherEntity[DataUpdateCoordinator[OpenMeteoForecast]]
):
    """Defines an Open-Meteo weather entity."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_native_precipitation_unit = UnitOfPrecipitationDepth.MILLIMETERS
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_DAILY | WeatherEntityFeature.FORECAST_HOURLY
    )

    def __init__(
        self,
        *,
        entry: OpenMeteoConfigEntry,
        coordinator: DataUpdateCoordinator[OpenMeteoForecast],
    ) -> None:
        """Initialize Open-Meteo weather entity."""
        super().__init__(coordinator=coordinator)
        self._attr_unique_id = entry.entry_id

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Open-Meteo",
            name=entry.title,
        )

    @property
    def condition(self) -> str | None:
        """Return the current condition."""
        if not self.coordinator.data.current_weather:
            return None
        return WMO_TO_HA_CONDITION_MAP.get(
            self.coordinator.data.current_weather.weather_code
        )

    @property
    def native_temperature(self) -> float | None:
        """Return the platform temperature."""
        if not self.coordinator.data.current_weather:
            return None
        return self.coordinator.data.current_weather.temperature

    @property
    def native_wind_speed(self) -> float | None:
        """Return the wind speed."""
        if not self.coordinator.data.current_weather:
            return None
        return self.coordinator.data.current_weather.wind_speed

    @property
    def wind_bearing(self) -> float | str | None:
        """Return the wind bearing."""
        if not self.coordinator.data.current_weather:
            return None
        return self.coordinator.data.current_weather.wind_direction

    @callback
    def _async_forecast_daily(self) -> list[Forecast] | None:
        """Return the daily forecast in native units."""
        if self.coordinator.data.daily is None:
            return None

        forecasts: list[Forecast] = []

        daily = self.coordinator.data.daily
        for index, date in enumerate(self.coordinator.data.daily.time):
            _datetime = datetime.combine(date=date, time=time(0), tzinfo=dt_util.UTC)
            forecast = Forecast(
                datetime=_datetime.isoformat(),
            )

            if daily.weathercode is not None:
                forecast[ATTR_FORECAST_CONDITION] = WMO_TO_HA_CONDITION_MAP.get(
                    daily.weathercode[index]
                )

            if daily.precipitation_sum is not None:
                forecast[ATTR_FORECAST_NATIVE_PRECIPITATION] = daily.precipitation_sum[
                    index
                ]

            if daily.temperature_2m_max is not None:
                forecast[ATTR_FORECAST_NATIVE_TEMP] = daily.temperature_2m_max[index]

            if daily.temperature_2m_min is not None:
                forecast[ATTR_FORECAST_NATIVE_TEMP_LOW] = daily.temperature_2m_min[
                    index
                ]

            if daily.wind_direction_10m_dominant is not None:
                forecast[ATTR_FORECAST_WIND_BEARING] = (
                    daily.wind_direction_10m_dominant[index]
                )

            if daily.wind_speed_10m_max is not None:
                forecast[ATTR_FORECAST_NATIVE_WIND_SPEED] = daily.wind_speed_10m_max[
                    index
                ]

            forecasts.append(forecast)

        return forecasts

    @callback
    def _async_forecast_hourly(self) -> list[Forecast] | None:
        """Return the daily forecast in native units."""
        if self.coordinator.data.hourly is None:
            return None

        forecasts: list[Forecast] = []

        # Can have data in the past: https://github.com/open-meteo/open-meteo/issues/699
        today = dt_util.utcnow()

        hourly = self.coordinator.data.hourly
        for index, _datetime in enumerate(self.coordinator.data.hourly.time):
            if _datetime.tzinfo is None:
                _datetime = _datetime.replace(tzinfo=dt_util.UTC)
            if _datetime < today:
                continue

            forecast = Forecast(
                datetime=_datetime.isoformat(),
            )

            if hourly.weather_code is not None:
                forecast[ATTR_FORECAST_CONDITION] = WMO_TO_HA_CONDITION_MAP.get(
                    hourly.weather_code[index]
                )

            if hourly.precipitation is not None:
                forecast[ATTR_FORECAST_NATIVE_PRECIPITATION] = hourly.precipitation[
                    index
                ]

            if hourly.temperature_2m is not None:
                forecast[ATTR_FORECAST_NATIVE_TEMP] = hourly.temperature_2m[index]

            forecasts.append(forecast)

        return forecasts
