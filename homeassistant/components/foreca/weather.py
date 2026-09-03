"""Weather platform for the Foreca integration."""

from typing import override

from pyforeca import DailyForecast, HourlyForecast

from homeassistant.components.weather import (
    Forecast,
    SingleCoordinatorWeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.const import (
    UnitOfLength,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import symbol_to_condition
from .coordinator import ForecaConfigEntry, ForecaUpdateCoordinator
from .entity import ForecaEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ForecaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a Foreca weather entity from a config entry."""
    async_add_entities([ForecaWeather(entry.runtime_data, entry)])


def _as_percentage(value: float | None) -> int | None:
    """Round a percentage the API may report with decimals to a whole percent."""
    if value is None:
        return None
    return round(value)


def _daily_to_forecast(day: DailyForecast) -> Forecast:
    """Convert a Foreca daily forecast to a Home Assistant forecast."""
    return Forecast(
        datetime=day.date or "",
        condition=symbol_to_condition(day.symbol),
        native_temperature=day.max_temp,
        native_templow=day.min_temp,
        native_precipitation=day.precip_accum,
        precipitation_probability=_as_percentage(day.precip_prob),
        native_wind_speed=day.max_wind_speed,
        native_wind_gust_speed=day.max_wind_gust,
        wind_bearing=day.wind_dir,
        native_pressure=day.pressure,
        native_dew_point=day.max_dew_point,
        uv_index=day.uv_index,
    )


def _hourly_to_forecast(hour: HourlyForecast) -> Forecast:
    """Convert a Foreca hourly forecast to a Home Assistant forecast."""
    return Forecast(
        datetime=hour.time or "",
        condition=symbol_to_condition(hour.symbol),
        native_temperature=hour.temperature,
        native_apparent_temperature=hour.feels_like_temp,
        native_precipitation=hour.precip_accum,
        precipitation_probability=_as_percentage(hour.precip_prob),
        native_wind_speed=hour.wind_speed,
        native_wind_gust_speed=hour.wind_gust,
        wind_bearing=hour.wind_dir,
        humidity=hour.rel_humidity,
        cloud_coverage=_as_percentage(hour.cloudiness),
        native_pressure=hour.pressure,
        native_dew_point=hour.dew_point,
        uv_index=hour.uv_index,
    )


class ForecaWeather(
    SingleCoordinatorWeatherEntity[ForecaUpdateCoordinator], ForecaEntity
):
    """Define a Foreca weather entity."""

    _attr_name = None
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND
    _attr_native_precipitation_unit = UnitOfPrecipitationDepth.MILLIMETERS
    _attr_native_visibility_unit = UnitOfLength.METERS
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_DAILY | WeatherEntityFeature.FORECAST_HOURLY
    )

    def __init__(
        self, coordinator: ForecaUpdateCoordinator, entry: ForecaConfigEntry
    ) -> None:
        """Initialize the weather entity."""
        super().__init__(coordinator)
        self._attr_unique_id = entry.entry_id

    @property
    @override
    def condition(self) -> str | None:
        """Return the current condition."""
        return symbol_to_condition(self.coordinator.data.current.symbol)

    @property
    @override
    def native_temperature(self) -> float | None:
        """Return the temperature."""
        return self.coordinator.data.current.temperature

    @property
    @override
    def native_apparent_temperature(self) -> float | None:
        """Return the apparent temperature."""
        return self.coordinator.data.current.feels_like_temp

    @property
    @override
    def native_dew_point(self) -> float | None:
        """Return the dew point."""
        return self.coordinator.data.current.dew_point

    @property
    @override
    def humidity(self) -> float | None:
        """Return the humidity."""
        return self.coordinator.data.current.rel_humidity

    @property
    @override
    def native_pressure(self) -> float | None:
        """Return the pressure."""
        return self.coordinator.data.current.pressure

    @property
    @override
    def native_wind_speed(self) -> float | None:
        """Return the wind speed."""
        return self.coordinator.data.current.wind_speed

    @property
    @override
    def native_wind_gust_speed(self) -> float | None:
        """Return the wind gust speed."""
        return self.coordinator.data.current.wind_gust

    @property
    @override
    def wind_bearing(self) -> float | None:
        """Return the wind bearing."""
        return self.coordinator.data.current.wind_dir

    @property
    @override
    def native_visibility(self) -> float | None:
        """Return the visibility."""
        return self.coordinator.data.current.visibility

    @property
    @override
    def cloud_coverage(self) -> float | None:
        """Return the cloud coverage."""
        return self.coordinator.data.current.cloudiness

    @property
    @override
    def uv_index(self) -> float | None:
        """Return the UV index."""
        return self.coordinator.data.current.uv_index

    @callback
    @override
    def _async_forecast_daily(self) -> list[Forecast] | None:
        """Return the daily forecast."""
        return [_daily_to_forecast(day) for day in self.coordinator.data.daily]

    @callback
    @override
    def _async_forecast_hourly(self) -> list[Forecast] | None:
        """Return the hourly forecast."""
        return [_hourly_to_forecast(hour) for hour in self.coordinator.data.hourly]
