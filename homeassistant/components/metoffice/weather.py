"""Support for UK Met Office weather service."""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from datapoint.Forecast import Forecast as ForecastData

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_IS_DAYTIME,
    ATTR_FORECAST_NATIVE_APPARENT_TEMP,
    ATTR_FORECAST_NATIVE_PRESSURE,
    ATTR_FORECAST_NATIVE_TEMP,
    ATTR_FORECAST_NATIVE_WIND_GUST_SPEED,
    ATTR_FORECAST_NATIVE_WIND_SPEED,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_UV_INDEX,
    ATTR_FORECAST_WIND_BEARING,
    DOMAIN as WEATHER_DOMAIN,
    CoordinatorWeatherEntity,
    Forecast,
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
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import TimestampDataUpdateCoordinator

from . import get_device_info
from .const import (
    ATTRIBUTION,
    DAILY_CONDITION_MAP,
    DOMAIN,
    HOURLY_CONDITION_MAP,
    METOFFICE_COORDINATES,
    METOFFICE_DAILY_COORDINATOR,
    METOFFICE_HOURLY_COORDINATOR,
    METOFFICE_NAME,
)
from .helpers import get_attribute


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
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
                hass_data,
            )
        ],
        False,
    )


def _build_hourly_forecast_data(timestep: dict[str, Any]) -> Forecast:
    data = Forecast(datetime=timestep["time"].isoformat())
    weather_code = get_attribute(timestep, "significantWeatherCode")
    if weather_code:
        data[ATTR_FORECAST_CONDITION] = HOURLY_CONDITION_MAP.get(weather_code)

    data[ATTR_FORECAST_NATIVE_APPARENT_TEMP] = get_attribute(
        timestep, "feelsLikeTemperature"
    )
    data[ATTR_FORECAST_NATIVE_PRESSURE] = get_attribute(timestep, "mslp")
    data[ATTR_FORECAST_NATIVE_TEMP] = get_attribute(timestep, "screenTemperature")
    data[ATTR_FORECAST_PRECIPITATION] = get_attribute(timestep, "totalPrecipAmount")
    data[ATTR_FORECAST_PRECIPITATION_PROBABILITY] = get_attribute(
        timestep, "probOfPrecipitation"
    )
    data[ATTR_FORECAST_UV_INDEX] = get_attribute(timestep, "uvIndex")
    data[ATTR_FORECAST_WIND_BEARING] = get_attribute(timestep, "windDirectionFrom10m")
    data[ATTR_FORECAST_NATIVE_WIND_SPEED] = get_attribute(timestep, "windSpeed10m")
    data[ATTR_FORECAST_NATIVE_WIND_GUST_SPEED] = get_attribute(
        timestep, "windGustSpeed10m"
    )

    return data


def _build_twice_daily_forecast_data(timestep: dict[str, Any]) -> Forecast:
    data = Forecast(datetime=timestep["time"].isoformat())
    data[ATTR_FORECAST_IS_DAYTIME] = abs(timestep["time"].hour - 12) <= 1
    weather_code = get_attribute(timestep, "SignificantWeatherCode")
    if weather_code:
        data[ATTR_FORECAST_CONDITION] = DAILY_CONDITION_MAP.get(weather_code)

    data[ATTR_FORECAST_NATIVE_APPARENT_TEMP] = get_attribute(
        timestep, "MaxFeelsLikeTemp"
    )
    data[ATTR_FORECAST_NATIVE_PRESSURE] = get_attribute(timestep, "Mslp")
    data[ATTR_FORECAST_NATIVE_TEMP] = get_attribute(timestep, "UpperBoundMaxTemp")
    data[ATTR_FORECAST_PRECIPITATION_PROBABILITY] = get_attribute(
        timestep, "ProbabilityOfPrecipitation"
    )
    data[ATTR_FORECAST_TEMP_LOW] = get_attribute(timestep, "LowerBoundMaxTemp")
    data[ATTR_FORECAST_UV_INDEX] = get_attribute(timestep, "maxUvIndex")
    data[ATTR_FORECAST_WIND_BEARING] = get_attribute(timestep, "10MWindDirection")
    data[ATTR_FORECAST_NATIVE_WIND_SPEED] = get_attribute(timestep, "10MWindSpeed")
    data[ATTR_FORECAST_NATIVE_WIND_GUST_SPEED] = get_attribute(timestep, "10MWindGust")
    return data


class MetOfficeWeather(
    CoordinatorWeatherEntity[
        TimestampDataUpdateCoordinator[ForecastData],
        TimestampDataUpdateCoordinator[ForecastData],
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
        WeatherEntityFeature.FORECAST_HOURLY | WeatherEntityFeature.FORECAST_TWICE_DAILY
    )

    def __init__(
        self,
        coordinator_daily: TimestampDataUpdateCoordinator[ForecastData],
        coordinator_hourly: TimestampDataUpdateCoordinator[ForecastData],
        hass_data: dict[str, Any],
    ) -> None:
        """Initialise the platform with a data instance."""
        observation_coordinator = coordinator_hourly
        super().__init__(
            observation_coordinator,
            daily_coordinator=coordinator_daily,
            hourly_coordinator=coordinator_hourly,
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

        if value:
            return HOURLY_CONDITION_MAP.get(value)
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
    def _async_forecast_twice_daily(self) -> list[Forecast] | None:
        """Return the twice daily forecast in native units."""
        coordinator = cast(
            TimestampDataUpdateCoordinator[ForecastData],
            self.forecast_coordinators["daily"],
        )
        timesteps = coordinator.data.timesteps
        return [
            _build_twice_daily_forecast_data(timestep)
            for timestep in timesteps
            if timestep["time"] > datetime.now(tz=timesteps[0]["time"].tzinfo)
        ]

    @callback
    def _async_forecast_hourly(self) -> list[Forecast] | None:
        """Return the hourly forecast in native units."""
        coordinator = cast(
            TimestampDataUpdateCoordinator[ForecastData],
            self.forecast_coordinators["hourly"],
        )

        timesteps = coordinator.data.timesteps
        return [
            _build_hourly_forecast_data(timestep)
            for timestep in timesteps
            if timestep["time"] > datetime.now(tz=timesteps[0]["time"].tzinfo)
        ]
