"""Support for UK Met Office weather service."""
from __future__ import annotations

from typing import Any, cast

from datapoint.Timestep import Timestep

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_NATIVE_TEMP,
    ATTR_FORECAST_NATIVE_WIND_SPEED,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_FORECAST_WIND_BEARING,
    DOMAIN as WEATHER_DOMAIN,
    CoordinatorWeatherEntity,
    Forecast,
    WeatherEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPressure, UnitOfSpeed, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import TimestampDataUpdateCoordinator

from . import get_device_info
from .const import (
    ATTRIBUTION,
    CONDITION_MAP,
    DOMAIN,
    METOFFICE_COORDINATES,
    METOFFICE_DAILY_COORDINATOR,
    METOFFICE_HOURLY_COORDINATOR,
    METOFFICE_NAME,
    MODE_DAILY,
)
from .data import MetOfficeData


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Met Office weather sensor platform."""
    entity_registry = er.async_get(hass)
    hass_data = hass.data[DOMAIN][entry.entry_id]

    entities = [
        MetOfficeWeather(
            hass_data[METOFFICE_DAILY_COORDINATOR],
            hass_data[METOFFICE_HOURLY_COORDINATOR],
            hass_data,
            False,
        )
    ]

    # Add hourly entity to legacy config entries
    if entity_registry.async_get_entity_id(
        WEATHER_DOMAIN,
        DOMAIN,
        _calculate_unique_id(hass_data[METOFFICE_COORDINATES], True),
    ):
        entities.append(
            MetOfficeWeather(
                hass_data[METOFFICE_DAILY_COORDINATOR],
                hass_data[METOFFICE_HOURLY_COORDINATOR],
                hass_data,
                True,
            )
        )

    async_add_entities(entities, False)


def _build_forecast_data(timestep: Timestep) -> Forecast:
    data = Forecast(datetime=timestep.date.isoformat())
    if timestep.weather:
        data[ATTR_FORECAST_CONDITION] = CONDITION_MAP.get(timestep.weather.value)
    if timestep.precipitation:
        data[ATTR_FORECAST_PRECIPITATION_PROBABILITY] = timestep.precipitation.value
    if timestep.temperature:
        data[ATTR_FORECAST_NATIVE_TEMP] = timestep.temperature.value
    if timestep.wind_direction:
        data[ATTR_FORECAST_WIND_BEARING] = timestep.wind_direction.value
    if timestep.wind_speed:
        data[ATTR_FORECAST_NATIVE_WIND_SPEED] = timestep.wind_speed.value
    return data


def _calculate_unique_id(coordinates: str, use_3hourly: bool) -> str:
    """Calculate unique ID."""
    if use_3hourly:
        return coordinates
    return f"{coordinates}_{MODE_DAILY}"


class MetOfficeWeather(
    CoordinatorWeatherEntity[
        TimestampDataUpdateCoordinator[MetOfficeData],
        TimestampDataUpdateCoordinator[MetOfficeData],
        TimestampDataUpdateCoordinator[MetOfficeData],
        TimestampDataUpdateCoordinator[MetOfficeData],  # Can be removed in Python 3.12
    ]
):
    """Implementation of a Met Office weather condition."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_wind_speed_unit = UnitOfSpeed.MILES_PER_HOUR
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_HOURLY | WeatherEntityFeature.FORECAST_DAILY
    )

    def __init__(
        self,
        coordinator_daily: TimestampDataUpdateCoordinator[MetOfficeData],
        coordinator_hourly: TimestampDataUpdateCoordinator[MetOfficeData],
        hass_data: dict[str, Any],
        use_3hourly: bool,
    ) -> None:
        """Initialise the platform with a data instance."""
        self._hourly = use_3hourly
        if use_3hourly:
            observation_coordinator = coordinator_hourly
        else:
            observation_coordinator = coordinator_daily
        super().__init__(
            observation_coordinator,
            daily_coordinator=coordinator_daily,
            hourly_coordinator=coordinator_hourly,
        )

        self._attr_device_info = get_device_info(
            coordinates=hass_data[METOFFICE_COORDINATES], name=hass_data[METOFFICE_NAME]
        )
        self._attr_name = "3-Hourly" if use_3hourly else "Daily"
        self._attr_unique_id = _calculate_unique_id(
            hass_data[METOFFICE_COORDINATES], use_3hourly
        )

    @property
    def condition(self) -> str | None:
        """Return the current condition."""
        if self.coordinator.data.now:
            return CONDITION_MAP.get(self.coordinator.data.now.weather.value)
        return None

    @property
    def native_temperature(self) -> float | None:
        """Return the platform temperature."""
        weather_now = self.coordinator.data.now
        if weather_now.temperature:
            value = weather_now.temperature.value
            return float(value) if value is not None else None
        return None

    @property
    def native_pressure(self) -> float | None:
        """Return the mean sea-level pressure."""
        weather_now = self.coordinator.data.now
        if weather_now and weather_now.pressure:
            value = weather_now.pressure.value
            return float(value) if value is not None else None
        return None

    @property
    def humidity(self) -> float | None:
        """Return the relative humidity."""
        weather_now = self.coordinator.data.now
        if weather_now and weather_now.humidity:
            value = weather_now.humidity.value
            return float(value) if value is not None else None
        return None

    @property
    def native_wind_speed(self) -> float | None:
        """Return the wind speed."""
        weather_now = self.coordinator.data.now
        if weather_now and weather_now.wind_speed:
            value = weather_now.wind_speed.value
            return float(value) if value is not None else None
        return None

    @property
    def wind_bearing(self) -> str | None:
        """Return the wind bearing."""
        weather_now = self.coordinator.data.now
        if weather_now and weather_now.wind_direction:
            value = weather_now.wind_direction.value
            return str(value) if value is not None else None
        return None

    @property
    def forecast(self) -> list[Forecast] | None:
        """Return the forecast array."""
        return [
            _build_forecast_data(timestep)
            for timestep in self.coordinator.data.forecast
        ]

    @callback
    def _async_forecast_daily(self) -> list[Forecast] | None:
        """Return the twice daily forecast in native units."""
        coordinator = cast(
            TimestampDataUpdateCoordinator[MetOfficeData],
            self.forecast_coordinators["daily"],
        )
        return [
            _build_forecast_data(timestep) for timestep in coordinator.data.forecast
        ]

    @callback
    def _async_forecast_hourly(self) -> list[Forecast] | None:
        """Return the hourly forecast in native units."""
        coordinator = cast(
            TimestampDataUpdateCoordinator[MetOfficeData],
            self.forecast_coordinators["hourly"],
        )
        return [
            _build_forecast_data(timestep) for timestep in coordinator.data.forecast
        ]
