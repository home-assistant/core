"""Support for UK Met Office weather service."""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from datapoint.Forecast import Forecast

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_IS_DAYTIME,
    ATTR_FORECAST_NATIVE_APPARENT_TEMP,
    ATTR_FORECAST_NATIVE_PRESSURE,
    ATTR_FORECAST_NATIVE_TEMP,
    ATTR_FORECAST_NATIVE_TEMP_LOW,
    ATTR_FORECAST_NATIVE_WIND_GUST_SPEED,
    ATTR_FORECAST_NATIVE_WIND_SPEED,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_FORECAST_UV_INDEX,
    ATTR_FORECAST_WIND_BEARING,
    DOMAIN as WEATHER_DOMAIN,
    CoordinatorWeatherEntity,
    Forecast as WeatherForecast,
    WeatherEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import TimestampDataUpdateCoordinator

from . import get_device_info
from .const import (
    ATTRIBUTION,
    CONDITION_MAP,
    DAILY_FORECAST_ATTRIBUTE_MAP,
    DAY_FORECAST_ATTRIBUTE_MAP,
    DOMAIN,
    HOURLY_FORECAST_ATTRIBUTE_MAP,
    METOFFICE_COORDINATES,
    METOFFICE_DAILY_COORDINATOR,
    METOFFICE_HOURLY_COORDINATOR,
    METOFFICE_NAME,
    METOFFICE_TWICE_DAILY_COORDINATOR,
    NIGHT_FORECAST_ATTRIBUTE_MAP,
)
from .helpers import get_attribute


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Met Office weather sensor platform."""
    entity_registry = er.async_get(hass)
    hass_data = hass.data[DOMAIN][entry.entry_id]

    # Remove daily entity from legacy config entries
    if entity_id := entity_registry.async_get_entity_id(
        WEATHER_DOMAIN,
        DOMAIN,
        f"{hass_data[METOFFICE_COORDINATES]}_daily",
    ):
        entity_registry.async_remove(entity_id)

    async_add_entities(
        [
            MetOfficeWeather(
                hass_data[METOFFICE_DAILY_COORDINATOR],
                hass_data[METOFFICE_HOURLY_COORDINATOR],
                hass_data[METOFFICE_TWICE_DAILY_COORDINATOR],
                hass_data,
            )
        ],
        False,
    )


def _build_hourly_forecast_data(timestep: dict[str, Any]) -> WeatherForecast:
    data = WeatherForecast(datetime=timestep["time"].isoformat())
    _populate_forecast_data(data, timestep, HOURLY_FORECAST_ATTRIBUTE_MAP)
    return data


def _build_daily_forecast_data(timestep: dict[str, Any]) -> WeatherForecast:
    data = WeatherForecast(datetime=timestep["time"].isoformat())
    _populate_forecast_data(data, timestep, DAILY_FORECAST_ATTRIBUTE_MAP)
    return data


def _build_twice_daily_forecast_data(timestep: dict[str, Any]) -> WeatherForecast:
    data = WeatherForecast(datetime=timestep["time"].isoformat())

    # day and night forecasts have slightly different format
    if "daySignificantWeatherCode" in timestep:
        data[ATTR_FORECAST_IS_DAYTIME] = True
        _populate_forecast_data(data, timestep, DAY_FORECAST_ATTRIBUTE_MAP)
    else:
        data[ATTR_FORECAST_IS_DAYTIME] = False
        _populate_forecast_data(data, timestep, NIGHT_FORECAST_ATTRIBUTE_MAP)
    return data


def _populate_forecast_data(
    forecast: WeatherForecast, timestep: dict[str, Any], mapping: dict[str, str]
) -> None:
    def get_mapped_attribute(attr: str) -> Any:
        if attr not in mapping:
            return None
        return get_attribute(timestep, mapping[attr])

    weather_code = get_mapped_attribute(ATTR_FORECAST_CONDITION)
    if weather_code is not None:
        forecast[ATTR_FORECAST_CONDITION] = CONDITION_MAP.get(weather_code)
    forecast[ATTR_FORECAST_NATIVE_APPARENT_TEMP] = get_mapped_attribute(
        ATTR_FORECAST_NATIVE_APPARENT_TEMP
    )
    forecast[ATTR_FORECAST_NATIVE_PRESSURE] = get_mapped_attribute(
        ATTR_FORECAST_NATIVE_PRESSURE
    )
    forecast[ATTR_FORECAST_NATIVE_TEMP] = get_mapped_attribute(
        ATTR_FORECAST_NATIVE_TEMP
    )
    forecast[ATTR_FORECAST_NATIVE_TEMP_LOW] = get_mapped_attribute(
        ATTR_FORECAST_NATIVE_TEMP_LOW
    )
    forecast[ATTR_FORECAST_PRECIPITATION] = get_mapped_attribute(
        ATTR_FORECAST_PRECIPITATION
    )
    forecast[ATTR_FORECAST_PRECIPITATION_PROBABILITY] = get_mapped_attribute(
        ATTR_FORECAST_PRECIPITATION_PROBABILITY
    )
    forecast[ATTR_FORECAST_UV_INDEX] = get_mapped_attribute(ATTR_FORECAST_UV_INDEX)
    forecast[ATTR_FORECAST_WIND_BEARING] = get_mapped_attribute(
        ATTR_FORECAST_WIND_BEARING
    )
    forecast[ATTR_FORECAST_NATIVE_WIND_SPEED] = get_mapped_attribute(
        ATTR_FORECAST_NATIVE_WIND_SPEED
    )
    forecast[ATTR_FORECAST_NATIVE_WIND_GUST_SPEED] = get_mapped_attribute(
        ATTR_FORECAST_NATIVE_WIND_GUST_SPEED
    )


class MetOfficeWeather(
    CoordinatorWeatherEntity[
        TimestampDataUpdateCoordinator[Forecast],
        TimestampDataUpdateCoordinator[Forecast],
        TimestampDataUpdateCoordinator[Forecast],
    ]
):
    """Implementation of a Met Office weather condition."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    _attr_name = None

    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_pressure_unit = UnitOfPressure.PA
    _attr_native_precipitation_unit = UnitOfLength.MILLIMETERS
    _attr_native_visibility_unit = UnitOfLength.METERS
    _attr_native_wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_HOURLY
        | WeatherEntityFeature.FORECAST_TWICE_DAILY
        | WeatherEntityFeature.FORECAST_DAILY
    )

    def __init__(
        self,
        coordinator_daily: TimestampDataUpdateCoordinator[Forecast],
        coordinator_hourly: TimestampDataUpdateCoordinator[Forecast],
        coordinator_twice_daily: TimestampDataUpdateCoordinator[Forecast],
        hass_data: dict[str, Any],
    ) -> None:
        """Initialise the platform with a data instance."""
        observation_coordinator = coordinator_hourly
        super().__init__(
            observation_coordinator,
            daily_coordinator=coordinator_daily,
            hourly_coordinator=coordinator_hourly,
            twice_daily_coordinator=coordinator_twice_daily,
        )

        self._attr_device_info = get_device_info(
            coordinates=hass_data[METOFFICE_COORDINATES], name=hass_data[METOFFICE_NAME]
        )
        self._attr_unique_id = hass_data[METOFFICE_COORDINATES]

    @property
    def condition(self) -> str | None:
        """Return the current condition."""
        weather_now = self.coordinator.data.now()
        value = get_attribute(weather_now, "significantWeatherCode")

        if value is not None:
            return CONDITION_MAP.get(value)
        return None

    @property
    def native_temperature(self) -> float | None:
        """Return the platform temperature."""
        weather_now = self.coordinator.data.now()
        value = get_attribute(weather_now, "screenTemperature")
        return float(value) if value is not None else None

    @property
    def native_dew_point(self) -> float | None:
        """Return the dew point."""
        weather_now = self.coordinator.data.now()
        value = get_attribute(weather_now, "screenDewPointTemperature")
        return float(value) if value is not None else None

    @property
    def native_pressure(self) -> float | None:
        """Return the mean sea-level pressure."""
        weather_now = self.coordinator.data.now()
        value = get_attribute(weather_now, "mslp")
        return float(value) if value is not None else None

    @property
    def humidity(self) -> float | None:
        """Return the relative humidity."""
        weather_now = self.coordinator.data.now()
        value = get_attribute(weather_now, "screenRelativeHumidity")
        return float(value) if value is not None else None

    @property
    def uv_index(self) -> float | None:
        """Return the UV index."""
        weather_now = self.coordinator.data.now()
        value = get_attribute(weather_now, "uvIndex")
        return float(value) if value is not None else None

    @property
    def native_visibility(self) -> float | None:
        """Return the visibility."""
        weather_now = self.coordinator.data.now()
        value = get_attribute(weather_now, "visibility")
        return float(value) if value is not None else None

    @property
    def native_wind_speed(self) -> float | None:
        """Return the wind speed."""
        weather_now = self.coordinator.data.now()
        value = get_attribute(weather_now, "windSpeed10m")
        return float(value) if value is not None else None

    @property
    def wind_bearing(self) -> float | None:
        """Return the wind bearing."""
        weather_now = self.coordinator.data.now()
        value = get_attribute(weather_now, "windDirectionFrom10m")
        return float(value) if value is not None else None

    @callback
    def _async_forecast_daily(self) -> list[WeatherForecast] | None:
        """Return the daily forecast in native units."""
        coordinator = cast(
            TimestampDataUpdateCoordinator[Forecast],
            self.forecast_coordinators["daily"],
        )
        timesteps = coordinator.data.timesteps
        return [
            _build_daily_forecast_data(timestep)
            for timestep in timesteps
            if timestep["time"] > datetime.now(tz=timesteps[0]["time"].tzinfo)
        ]

    @callback
    def _async_forecast_hourly(self) -> list[WeatherForecast] | None:
        """Return the hourly forecast in native units."""
        coordinator = cast(
            TimestampDataUpdateCoordinator[Forecast],
            self.forecast_coordinators["hourly"],
        )

        timesteps = coordinator.data.timesteps
        return [
            _build_hourly_forecast_data(timestep)
            for timestep in timesteps
            if timestep["time"] > datetime.now(tz=timesteps[0]["time"].tzinfo)
        ]

    @callback
    def _async_forecast_twice_daily(self) -> list[WeatherForecast] | None:
        """Return the twice daily forecast in native units."""
        coordinator = cast(
            TimestampDataUpdateCoordinator[Forecast],
            self.forecast_coordinators["twice_daily"],
        )
        timesteps = coordinator.data.timesteps
        return [
            _build_twice_daily_forecast_data(timestep)
            for timestep in timesteps
            if timestep["time"] > datetime.now(tz=timesteps[0]["time"].tzinfo)
        ]
