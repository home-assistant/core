"""Support for the AEMET OpenData service."""
from typing import Any, cast

from aemet_opendata.const import (
    AOD_CONDITION,
    AOD_FORECAST,
    AOD_FORECAST_DAILY,
    AOD_FORECAST_HOURLY,
    AOD_HUMIDITY,
    AOD_PRECIPITATION,
    AOD_PRECIPITATION_PROBABILITY,
    AOD_PRESSURE,
    AOD_TEMP,
    AOD_TEMP_MAX,
    AOD_TEMP_MIN,
    AOD_TIMESTAMP,
    AOD_TOWN,
    AOD_WEATHER,
    AOD_WIND_DIRECTION,
    AOD_WIND_SPEED,
    AOD_WIND_SPEED_MAX,
)

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_NATIVE_PRECIPITATION,
    ATTR_FORECAST_NATIVE_TEMP,
    ATTR_FORECAST_NATIVE_TEMP_LOW,
    ATTR_FORECAST_NATIVE_WIND_GUST_SPEED,
    ATTR_FORECAST_NATIVE_WIND_SPEED,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    DOMAIN as WEATHER_DOMAIN,
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
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTRIBUTION,
    CONDITIONS_MAP,
    DOMAIN,
    ENTRY_NAME,
    ENTRY_WEATHER_COORDINATOR,
    WEATHER_FORECAST_MODES,
)
from .entity import AemetEntity
from .weather_update_coordinator import WeatherUpdateCoordinator

FORECAST_MAP = {
    AOD_FORECAST_DAILY: {
        AOD_CONDITION: ATTR_FORECAST_CONDITION,
        AOD_PRECIPITATION_PROBABILITY: ATTR_FORECAST_PRECIPITATION_PROBABILITY,
        AOD_TEMP_MAX: ATTR_FORECAST_NATIVE_TEMP,
        AOD_TEMP_MIN: ATTR_FORECAST_NATIVE_TEMP_LOW,
        AOD_TIMESTAMP: ATTR_FORECAST_TIME,
        AOD_WIND_DIRECTION: ATTR_FORECAST_WIND_BEARING,
        AOD_WIND_SPEED: ATTR_FORECAST_NATIVE_WIND_SPEED,
    },
    AOD_FORECAST_HOURLY: {
        AOD_CONDITION: ATTR_FORECAST_CONDITION,
        AOD_PRECIPITATION_PROBABILITY: ATTR_FORECAST_PRECIPITATION_PROBABILITY,
        AOD_PRECIPITATION: ATTR_FORECAST_NATIVE_PRECIPITATION,
        AOD_TEMP: ATTR_FORECAST_NATIVE_TEMP,
        AOD_TIMESTAMP: ATTR_FORECAST_TIME,
        AOD_WIND_DIRECTION: ATTR_FORECAST_WIND_BEARING,
        AOD_WIND_SPEED_MAX: ATTR_FORECAST_NATIVE_WIND_GUST_SPEED,
        AOD_WIND_SPEED: ATTR_FORECAST_NATIVE_WIND_SPEED,
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
        f"{config_entry.unique_id} {WEATHER_FORECAST_MODES[AOD_FORECAST_HOURLY]}",
    ):
        for mode, mode_id in WEATHER_FORECAST_MODES.items():
            name = f"{domain_data[ENTRY_NAME]} {mode_id}"
            unique_id = f"{config_entry.unique_id} {mode_id}"
            entities.append(AemetWeather(name, unique_id, weather_coordinator, mode))
    else:
        entities.append(
            AemetWeather(
                domain_data[ENTRY_NAME],
                config_entry.unique_id,
                weather_coordinator,
                AOD_FORECAST_DAILY,
            )
        )

    async_add_entities(entities, False)


class AemetWeather(
    AemetEntity,
    SingleCoordinatorWeatherEntity[WeatherUpdateCoordinator],
):
    """Implementation of an AEMET OpenData weather."""

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
            self._forecast_mode == AOD_FORECAST_DAILY
        )
        self._attr_name = name
        self._attr_unique_id = unique_id

    @property
    def condition(self):
        """Return the current condition."""
        cond = self.get_aemet_value([AOD_WEATHER, AOD_CONDITION])
        return CONDITIONS_MAP.get(cond)

    def _forecast(self, forecast_mode: str) -> list[Forecast]:
        """Return the forecast array."""
        forecasts = self.get_aemet_value([AOD_TOWN, forecast_mode, AOD_FORECAST])
        forecast_map = FORECAST_MAP[forecast_mode]
        forecast_list: list[dict[str, Any]] = []
        for forecast in forecasts:
            cur_forecast: dict[str, Any] = {}
            for api_key, ha_key in forecast_map.items():
                value = forecast[api_key]
                if api_key == AOD_CONDITION:
                    value = CONDITIONS_MAP.get(value)
                cur_forecast[ha_key] = value
            forecast_list += [cur_forecast]
        return cast(list[Forecast], forecast_list)

    @property
    def forecast(self) -> list[Forecast]:
        """Return the forecast array."""
        return self._forecast(self._forecast_mode)

    @callback
    def _async_forecast_daily(self) -> list[Forecast]:
        """Return the daily forecast in native units."""
        return self._forecast(AOD_FORECAST_DAILY)

    @callback
    def _async_forecast_hourly(self) -> list[Forecast]:
        """Return the hourly forecast in native units."""
        return self._forecast(AOD_FORECAST_HOURLY)

    @property
    def humidity(self):
        """Return the humidity."""
        return self.get_aemet_value([AOD_WEATHER, AOD_HUMIDITY])

    @property
    def native_pressure(self):
        """Return the pressure."""
        return self.get_aemet_value([AOD_WEATHER, AOD_PRESSURE])

    @property
    def native_temperature(self):
        """Return the temperature."""
        return self.get_aemet_value([AOD_WEATHER, AOD_TEMP])

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        return self.get_aemet_value([AOD_WEATHER, AOD_WIND_DIRECTION])

    @property
    def native_wind_gust_speed(self):
        """Return the wind gust speed in native units."""
        return self.get_aemet_value([AOD_WEATHER, AOD_WIND_SPEED_MAX])

    @property
    def native_wind_speed(self):
        """Return the wind speed."""
        return self.get_aemet_value([AOD_WEATHER, AOD_WIND_SPEED])
