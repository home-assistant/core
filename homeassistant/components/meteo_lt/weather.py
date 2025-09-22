"""Weather platform for Meteo.lt integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.weather import (
    Forecast,
    WeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MeteoLtConfigEntry
from .const import ATTRIBUTION, CONDITION_MAP, DOMAIN
from .coordinator import MeteoLtUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeteoLtConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the weather platform."""
    coordinator = entry.runtime_data

    async_add_entities([MeteoLtWeatherEntity(coordinator, entry)])


class MeteoLtWeatherEntity(CoordinatorEntity[MeteoLtUpdateCoordinator], WeatherEntity):
    """Weather entity for Meteo.lt."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_attribution = ATTRIBUTION
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_precipitation_unit = UnitOfPrecipitationDepth.MILLIMETERS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_DAILY | WeatherEntityFeature.FORECAST_HOURLY
    )

    def __init__(
        self,
        coordinator: MeteoLtUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the weather entity."""
        super().__init__(coordinator)

        place_code = coordinator.place_code
        self._attr_unique_id = f"{place_code}_weather"

        # Create device info with configured name
        device_name = entry.data.get(CONF_NAME, coordinator.place_code)
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, place_code)},
            manufacturer="Lithuanian Hydrometeorological Service",
            model="Weather Station",
            name=device_name,
        )

    @property
    def native_temperature(self) -> float | None:
        """Return the temperature."""
        if self.coordinator.data and self.coordinator.data.current_forecast:
            return self.coordinator.data.current_forecast.air_temperature
        return None

    @property
    def native_apparent_temperature(self) -> float | None:
        """Return the apparent temperature."""
        if self.coordinator.data and self.coordinator.data.current_forecast:
            return self.coordinator.data.current_forecast.feels_like_temperature
        return None

    @property
    def humidity(self) -> int | None:
        """Return the humidity."""
        if self.coordinator.data and self.coordinator.data.current_forecast:
            return self.coordinator.data.current_forecast.relative_humidity
        return None

    @property
    def native_pressure(self) -> float | None:
        """Return the pressure."""
        if self.coordinator.data and self.coordinator.data.current_forecast:
            return self.coordinator.data.current_forecast.sea_level_pressure
        return None

    @property
    def native_wind_speed(self) -> float | None:
        """Return the wind speed."""
        if self.coordinator.data and self.coordinator.data.current_forecast:
            return self.coordinator.data.current_forecast.wind_speed
        return None

    @property
    def wind_bearing(self) -> int | None:
        """Return the wind bearing."""
        if self.coordinator.data and self.coordinator.data.current_forecast:
            return self.coordinator.data.current_forecast.wind_direction
        return None

    @property
    def native_wind_gust_speed(self) -> float | None:
        """Return the wind gust speed."""
        if self.coordinator.data and self.coordinator.data.current_forecast:
            return self.coordinator.data.current_forecast.wind_gust
        return None

    @property
    def cloud_coverage(self) -> int | None:
        """Return the cloud coverage."""
        if self.coordinator.data and self.coordinator.data.current_forecast:
            return self.coordinator.data.current_forecast.cloud_cover
        return None

    @property
    def condition(self) -> str | None:
        """Return the current condition."""
        if (
            self.coordinator.data
            and self.coordinator.data.current_forecast
            and self.coordinator.data.current_forecast.condition_code
        ):
            condition_code = self.coordinator.data.current_forecast.condition_code
            return CONDITION_MAP.get(condition_code)
        return None

    async def async_forecast_daily(self) -> list[Forecast] | None:
        """Return the daily forecast."""
        if not self.coordinator.data:
            return None

        daily_forecasts = self.coordinator.data.get_daily_forecasts(5)
        forecasts: list[Forecast] = []

        for forecast_data in daily_forecasts:
            forecast = Forecast(
                datetime=forecast_data.forecast_time_utc.isoformat(),
                native_temperature=forecast_data.air_temperature,
                native_templow=forecast_data.air_temperature_low,
                native_apparent_temperature=forecast_data.feels_like_temperature,
                condition=CONDITION_MAP.get(forecast_data.condition_code),
                native_precipitation=forecast_data.total_precipitation,
                precipitation_probability=None,  # Not provided by API
                native_wind_speed=forecast_data.wind_speed,
                wind_bearing=forecast_data.wind_direction,
                cloud_coverage=forecast_data.cloud_cover,
            )
            forecasts.append(forecast)

        return forecasts

    async def async_forecast_hourly(self) -> list[Forecast] | None:
        """Return the hourly forecast."""
        if not self.coordinator.data:
            return None

        forecasts: list[Forecast] = []

        # Get next 24 hours of forecasts
        for forecast_data in self.coordinator.data.forecast_timestamps[:24]:
            forecast = Forecast(
                datetime=forecast_data.forecast_time_utc.isoformat(),
                native_temperature=forecast_data.air_temperature,
                native_apparent_temperature=forecast_data.feels_like_temperature,
                condition=CONDITION_MAP.get(forecast_data.condition_code),
                native_precipitation=forecast_data.total_precipitation,
                precipitation_probability=None,  # Not provided by API
                native_wind_speed=forecast_data.wind_speed,
                wind_bearing=forecast_data.wind_direction,
                cloud_coverage=forecast_data.cloud_cover,
            )
            forecasts.append(forecast)

        return forecasts

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        if not self.coordinator.data:
            return None

        place = self.coordinator.data.place
        current = self.coordinator.data.current_forecast

        attributes = {
            "place_code": place.code,
            "place_name": place.name,
            "administrative_division": place.administrative_division,
            "country": place.country or "Lithuania",
            "forecast_creation_time": self.coordinator.data.forecast_creation_time_utc.isoformat(),
        }

        if current:
            attributes["forecast_time"] = current.forecast_time_utc.isoformat()

        return attributes
