"""Support for MeteoSwiss weather service."""

import datetime

import meteoswiss_async

from homeassistant.components.weather import (
    Forecast,
    SingleCoordinatorWeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.const import (
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MeteoSwissConfigEntry
from .const import DOMAIN, LOCATION_NAME, POSTAL_CODE, POSTAL_CODE_ADDITIONAL_NUMBER
from .coordinator import MeteoSwissDataUpdateCoordinator

DEFAULT_NAME = "MeteoSwiss"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MeteoSwissConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add a weather entity from a config_entry."""
    coordinator = config_entry.runtime_data

    entities = [MeteoSwissWeather(coordinator, config_entry)]

    async_add_entities(entities)


class MeteoSwissWeather(
    SingleCoordinatorWeatherEntity[MeteoSwissDataUpdateCoordinator]
):
    """Implementation of a MeteoSwiss weather condition."""

    _attr_attribution = (
        "Weather forecast from MeteoSwiss, delivered by the Swiss "
        "Meteorological Institute."
    )
    _attr_has_entity_name = True
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_precipitation_unit = UnitOfPrecipitationDepth.MILLIMETERS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_DAILY | WeatherEntityFeature.FORECAST_HOURLY
    )

    def __init__(
        self,
        coordinator: MeteoSwissDataUpdateCoordinator,
        config_entry: MeteoSwissConfigEntry,
    ) -> None:
        """Initialise the platform with a data instance and site."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{config_entry.data[POSTAL_CODE]}{config_entry.data[POSTAL_CODE_ADDITIONAL_NUMBER]:02d}"
        self._config = config_entry.data
        self._attr_device_info = DeviceInfo(
            name="Forecast",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, config_entry.entry_id)},
            manufacturer="MeteoSwiss",
            model="Location Forecast",
            configuration_url="https://www.meteoswiss.admin.ch/",
        )
        self._attr_name = self._config[LOCATION_NAME]

    @property
    def condition(self) -> str | None:
        """Return the current condition."""
        return meteoswiss_async.Condition.from_icon(
            self.coordinator.data.weather.current_weather.icon
        )

    @property
    def native_temperature(self) -> float | None:
        """Return the temperature."""
        return float(self.coordinator.data.weather.current_weather.temperature)

    @callback
    def _async_forecast_daily(self) -> list[Forecast] | None:
        """Return the daily forecast in native units."""
        return [
            Forecast(
                datetime=day.day_date,
                condition=day.condition,
                native_temperature=day.temperature_max,
                native_templow=day.temperature_min,
                native_precipitation=day.precipitation,
            )
            for day in self.coordinator.data.weather.forecast
        ]

    @callback
    def _async_forecast_hourly(self) -> list[Forecast] | None:
        """Return the hourly forecast in native units."""
        forecast: list[Forecast] = []
        graph: meteoswiss_async.Graph = self.coordinator.data.weather.graph
        start_time = graph.start.to_datetime()
        for i in range(graph.num_entry_hours):
            forecast.append(
                Forecast(
                    datetime=str(start_time),
                    condition=graph.weather_condition_3h[i // 3],
                    native_temperature=graph.temperature_max_1h[i],
                    native_templow=graph.temperature_min_1h[i],
                    native_precipitation=graph.precipitation_mean_1h,
                    native_wind_speed=graph.wind_speed_3h[i // 3],
                    wind_bearing=graph.wind_direction_3h[i // 3],
                )
            )
            start_time += datetime.timedelta(hours=1)
        return forecast
