"""Support for the AEMET OpenData service."""
from typing import cast

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_NATIVE_PRECIPITATION,
    ATTR_FORECAST_NATIVE_TEMP,
    ATTR_FORECAST_NATIVE_TEMP_LOW,
    ATTR_FORECAST_NATIVE_WIND_SPEED,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    DOMAIN as WEATHER_DOMAIN,
    CoordinatorWeatherEntity,
    Forecast,
    WeatherEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_API_CONDITION,
    ATTR_API_FORECAST_CONDITION,
    ATTR_API_FORECAST_PRECIPITATION,
    ATTR_API_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_API_FORECAST_TEMP,
    ATTR_API_FORECAST_TEMP_LOW,
    ATTR_API_FORECAST_TIME,
    ATTR_API_FORECAST_WIND_BEARING,
    ATTR_API_FORECAST_WIND_SPEED,
    ATTR_API_HUMIDITY,
    ATTR_API_PRESSURE,
    ATTR_API_TEMPERATURE,
    ATTR_API_WIND_BEARING,
    ATTR_API_WIND_SPEED,
    ATTRIBUTION,
    DOMAIN,
    ENTRY_NAME,
    ENTRY_WEATHER_COORDINATOR,
    FORECAST_MODE_ATTR_API,
    FORECAST_MODE_DAILY,
    FORECAST_MODE_HOURLY,
    FORECAST_MODES,
)
from .weather_update_coordinator import WeatherUpdateCoordinator

FORECAST_MAP = {
    FORECAST_MODE_DAILY: {
        ATTR_API_FORECAST_CONDITION: ATTR_FORECAST_CONDITION,
        ATTR_API_FORECAST_PRECIPITATION_PROBABILITY: ATTR_FORECAST_PRECIPITATION_PROBABILITY,
        ATTR_API_FORECAST_TEMP_LOW: ATTR_FORECAST_NATIVE_TEMP_LOW,
        ATTR_API_FORECAST_TEMP: ATTR_FORECAST_NATIVE_TEMP,
        ATTR_API_FORECAST_TIME: ATTR_FORECAST_TIME,
        ATTR_API_FORECAST_WIND_BEARING: ATTR_FORECAST_WIND_BEARING,
        ATTR_API_FORECAST_WIND_SPEED: ATTR_FORECAST_NATIVE_WIND_SPEED,
    },
    FORECAST_MODE_HOURLY: {
        ATTR_API_FORECAST_CONDITION: ATTR_FORECAST_CONDITION,
        ATTR_API_FORECAST_PRECIPITATION_PROBABILITY: ATTR_FORECAST_PRECIPITATION_PROBABILITY,
        ATTR_API_FORECAST_PRECIPITATION: ATTR_FORECAST_NATIVE_PRECIPITATION,
        ATTR_API_FORECAST_TEMP: ATTR_FORECAST_NATIVE_TEMP,
        ATTR_API_FORECAST_TIME: ATTR_FORECAST_TIME,
        ATTR_API_FORECAST_WIND_BEARING: ATTR_FORECAST_WIND_BEARING,
        ATTR_API_FORECAST_WIND_SPEED: ATTR_FORECAST_NATIVE_WIND_SPEED,
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AEMET OpenData weather entity based on a config entry."""
    domain_data = hass.data[DOMAIN][config_entry.entry_id]
    weather_coordinator = domain_data[ENTRY_WEATHER_COORDINATOR]

    entities = []
    entity_registry = er.async_get(hass)

    # Add daily + hourly entity for legacy config entries, only add daily for new
    # config entries. This can be removed in HA Core 2024.3
    if entity_registry.async_get_entity_id(
        WEATHER_DOMAIN,
        DOMAIN,
        f"{config_entry.unique_id} {FORECAST_MODE_HOURLY}",
    ):
        for mode in FORECAST_MODES:
            name = f"{domain_data[ENTRY_NAME]} {mode}"
            unique_id = f"{config_entry.unique_id} {mode}"
            entities.append(AemetWeather(name, unique_id, weather_coordinator, mode))
    else:
        entities.append(
            AemetWeather(
                domain_data[ENTRY_NAME],
                config_entry.unique_id,
                weather_coordinator,
                FORECAST_MODE_DAILY,
            )
        )

    async_add_entities(entities, False)


class AemetWeather(CoordinatorWeatherEntity[WeatherUpdateCoordinator]):
    """Implementation of an AEMET OpenData sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_native_precipitation_unit = UnitOfPrecipitationDepth.MILLIMETERS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_DAILY | WeatherEntityFeature.FORECAST_HOURLY
    )

    def __init__(
        self,
        name,
        unique_id,
        coordinator: WeatherUpdateCoordinator,
        forecast_mode,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._forecast_mode = forecast_mode
        self._attr_entity_registry_enabled_default = (
            self._forecast_mode == FORECAST_MODE_DAILY
        )
        self._attr_name = name
        self._attr_unique_id = unique_id

    @property
    def condition(self):
        """Return the current condition."""
        return self.coordinator.data[ATTR_API_CONDITION]

    def _forecast(self, forecast_mode: str) -> list[Forecast]:
        """Return the forecast array."""
        forecasts = self.coordinator.data[FORECAST_MODE_ATTR_API[forecast_mode]]
        forecast_map = FORECAST_MAP[forecast_mode]
        return cast(
            list[Forecast],
            [
                {ha_key: forecast[api_key] for api_key, ha_key in forecast_map.items()}
                for forecast in forecasts
            ],
        )

    @property
    def forecast(self) -> list[Forecast]:
        """Return the forecast array."""
        return self._forecast(self._forecast_mode)

    async def async_forecast_daily(self) -> list[Forecast]:
        """Return the daily forecast in native units."""
        return self._forecast(FORECAST_MODE_DAILY)

    async def async_forecast_hourly(self) -> list[Forecast]:
        """Return the hourly forecast in native units."""
        return self._forecast(FORECAST_MODE_HOURLY)

    @property
    def humidity(self):
        """Return the humidity."""
        return self.coordinator.data[ATTR_API_HUMIDITY]

    @property
    def native_pressure(self):
        """Return the pressure."""
        return self.coordinator.data[ATTR_API_PRESSURE]

    @property
    def native_temperature(self):
        """Return the temperature."""
        return self.coordinator.data[ATTR_API_TEMPERATURE]

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        return self.coordinator.data[ATTR_API_WIND_BEARING]

    @property
    def native_wind_speed(self):
        """Return the wind speed."""
        return self.coordinator.data[ATTR_API_WIND_SPEED]
