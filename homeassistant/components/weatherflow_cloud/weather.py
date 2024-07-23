"""Support for WeatherFlow Forecast weather service."""

from __future__ import annotations

from weatherflow4py.models.rest.unified import WeatherFlowDataREST

from homeassistant.components.weather import (
    Forecast,
    SingleCoordinatorWeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, STATE_MAP
from .coordinator import WeatherFlowCloudDataUpdateCoordinator
from .entity import WeatherFlowCloudEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add a weather entity from a config_entry."""
    coordinator: WeatherFlowCloudDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    async_add_entities(
        [
            WeatherFlowWeather(coordinator, station_id=station_id)
            for station_id, data in coordinator.data.items()
        ]
    )


class WeatherFlowWeather(
    WeatherFlowCloudEntity,
    SingleCoordinatorWeatherEntity[WeatherFlowCloudDataUpdateCoordinator],
):
    """Implementation of a WeatherFlow weather condition."""

    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_precipitation_unit = UnitOfPrecipitationDepth.MILLIMETERS
    _attr_native_pressure_unit = UnitOfPressure.MBAR
    _attr_native_wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_DAILY | WeatherEntityFeature.FORECAST_HOURLY
    )
    _attr_name = None

    def __init__(
        self,
        coordinator: WeatherFlowCloudDataUpdateCoordinator,
        station_id: int,
    ) -> None:
        """Initialise the platform with a data instance and station."""
        super().__init__(coordinator, station_id)
        self._attr_unique_id = f"weatherflow_forecast_{station_id}"

    @property
    def local_data(self) -> WeatherFlowDataREST:
        """Return the local weather data object for this station."""
        return self.coordinator.data[self.station_id]

    @property
    def condition(self) -> str | None:
        """Return current condition - required property."""
        return STATE_MAP[self.local_data.weather.current_conditions.icon.value]

    @property
    def native_temperature(self) -> float | None:
        """Return the temperature."""
        return self.local_data.weather.current_conditions.air_temperature

    @property
    def native_pressure(self) -> float | None:
        """Return the Air Pressure @ Station."""
        return self.local_data.weather.current_conditions.station_pressure

    @property
    def humidity(self) -> float | None:
        """Return the humidity."""
        return self.local_data.weather.current_conditions.relative_humidity

    @property
    def native_wind_speed(self) -> float | None:
        """Return the wind speed."""
        return self.local_data.weather.current_conditions.wind_avg

    @property
    def wind_bearing(self) -> float | str | None:
        """Return the wind direction."""
        return self.local_data.weather.current_conditions.wind_direction

    @property
    def native_wind_gust_speed(self) -> float | None:
        """Return the wind gust speed in native units."""
        return self.local_data.weather.current_conditions.wind_gust

    @property
    def native_dew_point(self) -> float | None:
        """Return dew point."""
        return self.local_data.weather.current_conditions.dew_point

    @property
    def uv_index(self) -> float | None:
        """Return UV Index."""
        return self.local_data.weather.current_conditions.uv

    @callback
    def _async_forecast_daily(self) -> list[Forecast] | None:
        """Return the daily forecast in native units."""
        return [x.ha_forecast for x in self.local_data.weather.forecast.daily]

    @callback
    def _async_forecast_hourly(self) -> list[Forecast] | None:
        """Return the hourly forecast in native units."""
        return [x.ha_forecast for x in self.local_data.weather.forecast.hourly]
