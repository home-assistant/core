"""Weather entity with cached daily and hourly forecasts."""

from typing import override

from homeassistant.components.weather import (
    Forecast,
    SingleCoordinatorWeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.const import (
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import ForecastData
from .coordinator import XiaomiWeatherConfigEntry, XiaomiWeatherCoordinator
from .entity import XiaomiWeatherEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: XiaomiWeatherConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the location's weather entity."""
    async_add_entities([XiaomiWeather(entry)])


def _forecast(items: tuple[ForecastData, ...]) -> list[Forecast]:
    """Return fresh mappings so consumers cannot mutate the shared snapshot."""
    result: list[Forecast] = []
    for item in items:
        forecast: Forecast = {
            "datetime": item.time.isoformat(),
            "native_temperature": item.temperature,
        }
        if item.condition is not None:
            forecast["condition"] = item.condition
        if item.low is not None:
            forecast["native_templow"] = item.low
        if item.wind_speed is not None:
            forecast["native_wind_speed"] = item.wind_speed
        if item.wind_bearing is not None:
            forecast["wind_bearing"] = item.wind_bearing
        if item.precipitation_probability is not None:
            forecast["precipitation_probability"] = item.precipitation_probability
        if item.is_daytime is not None:
            forecast["is_daytime"] = item.is_daytime
        result.append(forecast)
    return result


class XiaomiWeather(
    XiaomiWeatherEntity, SingleCoordinatorWeatherEntity[XiaomiWeatherCoordinator]
):
    """Represent Xiaomi Weather for one city."""

    _attr_name = None
    _attr_attribution = "Weather data provided by Xiaomi Weather"
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_native_visibility_unit = UnitOfLength.KILOMETERS
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_DAILY
        | WeatherEntityFeature.FORECAST_HOURLY
        | WeatherEntityFeature.FORECAST_TWICE_DAILY
    )

    def __init__(self, entry: XiaomiWeatherConfigEntry) -> None:
        """Initialize the weather entity."""
        super().__init__(entry, "weather")

    @property
    @override
    def condition(self) -> str | None:
        """Return the normalized current condition."""
        return self.coordinator.data.condition

    @property
    @override
    def native_temperature(self) -> float:
        """Return temperature in Celsius."""
        return self.coordinator.data.temperature

    @property
    @override
    def humidity(self) -> float | None:
        """Return relative humidity."""
        return self.coordinator.data.humidity

    @property
    @override
    def native_pressure(self) -> float | None:
        """Return pressure in hPa."""
        return self.coordinator.data.pressure

    @property
    @override
    def native_wind_speed(self) -> float | None:
        """Return wind speed in km/h."""
        return self.coordinator.data.wind_speed

    @property
    @override
    def wind_bearing(self) -> float | None:
        """Return wind direction in degrees."""
        return self.coordinator.data.wind_bearing

    @property
    @override
    def native_apparent_temperature(self) -> float | None:
        """Return feels-like temperature in Celsius."""
        return self.coordinator.data.apparent_temperature

    @property
    @override
    def uv_index(self) -> float | None:
        """Return the UV index."""
        return self.coordinator.data.uv_index

    @property
    @override
    def native_visibility(self) -> float | None:
        """Return visibility only when the source provides a valid km value."""
        return self.coordinator.data.visibility

    @callback
    @override
    def _async_forecast_twice_daily(self) -> list[Forecast]:
        """Return daytime highs and nighttime lows, anchored to solar times."""
        return _forecast(self.coordinator.data.twice_daily)

    @callback
    @override
    def _async_forecast_daily(self) -> list[Forecast]:
        """Return the cached daily forecast."""
        return _forecast(self.coordinator.data.daily)

    @callback
    @override
    def _async_forecast_hourly(self) -> list[Forecast]:
        """Return the cached hourly forecast."""
        return _forecast(self.coordinator.data.hourly)
