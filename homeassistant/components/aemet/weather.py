"""Support for the AEMET OpenData service."""
from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_NATIVE_PRECIPITATION,
    ATTR_FORECAST_NATIVE_TEMP,
    ATTR_FORECAST_NATIVE_TEMP_LOW,
    ATTR_FORECAST_NATIVE_WIND_SPEED,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    WeatherEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    LENGTH_MILLIMETERS,
    PRESSURE_HPA,
    SPEED_KILOMETERS_PER_HOUR,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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
    for mode in FORECAST_MODES:
        name = f"{domain_data[ENTRY_NAME]} {mode}"
        unique_id = f"{config_entry.unique_id} {mode}"
        entities.append(AemetWeather(name, unique_id, weather_coordinator, mode))

    async_add_entities(entities, False)


class AemetWeather(CoordinatorEntity[WeatherUpdateCoordinator], WeatherEntity):
    """Implementation of an AEMET OpenData sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_native_precipitation_unit = LENGTH_MILLIMETERS
    _attr_native_pressure_unit = PRESSURE_HPA
    _attr_native_temperature_unit = TEMP_CELSIUS
    _attr_native_wind_speed_unit = SPEED_KILOMETERS_PER_HOUR

    def __init__(
        self,
        name,
        unique_id,
        coordinator: WeatherUpdateCoordinator,
        forecast_mode,
    ):
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

    @property
    def forecast(self):
        """Return the forecast array."""
        forecasts = self.coordinator.data[FORECAST_MODE_ATTR_API[self._forecast_mode]]
        forecast_map = FORECAST_MAP[self._forecast_mode]
        return [
            {ha_key: forecast[api_key] for api_key, ha_key in forecast_map.items()}
            for forecast in forecasts
        ]

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
