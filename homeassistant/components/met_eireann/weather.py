"""Support for Met Éireann weather service."""
import logging
from types import MappingProxyType
from typing import Any, cast

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_TIME,
    DOMAIN as WEATHER_DOMAIN,
    Forecast,
    SingleCoordinatorWeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from . import MetEireannWeatherData
from .const import CONDITION_MAP, DEFAULT_NAME, DOMAIN, FORECAST_MAP

_LOGGER = logging.getLogger(__name__)


def format_condition(condition: str | None) -> str | None:
    """Map the conditions provided by the weather API to those supported by the frontend."""
    if condition is not None:
        for key, value in CONDITION_MAP.items():
            if condition in value:
                return key
    return condition


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add a weather entity from a config_entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    entity_registry = er.async_get(hass)

    entities = [MetEireannWeather(coordinator, config_entry.data, False)]

    # Add hourly entity to legacy config entries
    if entity_registry.async_get_entity_id(
        WEATHER_DOMAIN,
        DOMAIN,
        _calculate_unique_id(config_entry.data, True),
    ):
        entities.append(MetEireannWeather(coordinator, config_entry.data, True))

    async_add_entities(entities)


def _calculate_unique_id(config: MappingProxyType[str, Any], hourly: bool) -> str:
    """Calculate unique ID."""
    name_appendix = ""
    if hourly:
        name_appendix = "-hourly"

    return f"{config[CONF_LATITUDE]}-{config[CONF_LONGITUDE]}{name_appendix}"


class MetEireannWeather(
    SingleCoordinatorWeatherEntity[DataUpdateCoordinator[MetEireannWeatherData]]
):
    """Implementation of a Met Éireann weather condition."""

    _attr_attribution = "Data provided by Met Éireann"
    _attr_native_precipitation_unit = UnitOfPrecipitationDepth.MILLIMETERS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_DAILY | WeatherEntityFeature.FORECAST_HOURLY
    )

    def __init__(self, coordinator, config, hourly):
        """Initialise the platform with a data instance and site."""
        super().__init__(coordinator)
        self._attr_unique_id = _calculate_unique_id(config, hourly)
        self._config = config
        self._hourly = hourly

    @property
    def name(self):
        """Return the name of the sensor."""
        name = self._config.get(CONF_NAME)
        name_appendix = ""
        if self._hourly:
            name_appendix = " Hourly"

        if name is not None:
            return f"{name}{name_appendix}"

        return f"{DEFAULT_NAME}{name_appendix}"

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return not self._hourly

    @property
    def condition(self):
        """Return the current condition."""
        return format_condition(
            self.coordinator.data.current_weather_data.get("condition")
        )

    @property
    def native_temperature(self):
        """Return the temperature."""
        return self.coordinator.data.current_weather_data.get("temperature")

    @property
    def native_pressure(self):
        """Return the pressure."""
        return self.coordinator.data.current_weather_data.get("pressure")

    @property
    def humidity(self):
        """Return the humidity."""
        return self.coordinator.data.current_weather_data.get("humidity")

    @property
    def native_wind_speed(self):
        """Return the wind speed."""
        return self.coordinator.data.current_weather_data.get("wind_speed")

    @property
    def wind_bearing(self):
        """Return the wind direction."""
        return self.coordinator.data.current_weather_data.get("wind_bearing")

    def _forecast(self, hourly: bool) -> list[Forecast]:
        """Return the forecast array."""
        if hourly:
            me_forecast = self.coordinator.data.hourly_forecast
        else:
            me_forecast = self.coordinator.data.daily_forecast
        required_keys = {"temperature", "datetime"}

        ha_forecast: list[Forecast] = []

        for item in me_forecast:
            if not set(item).issuperset(required_keys):
                continue
            ha_item: Forecast = cast(
                Forecast,
                {
                    k: item[v]
                    for k, v in FORECAST_MAP.items()
                    if item.get(v) is not None
                },
            )
            # Convert condition
            if item.get("condition"):
                ha_item[ATTR_FORECAST_CONDITION] = format_condition(item["condition"])
            # Convert timestamp to UTC string
            if item.get("datetime"):
                ha_item[ATTR_FORECAST_TIME] = dt_util.as_utc(
                    item["datetime"]
                ).isoformat()
            ha_forecast.append(ha_item)
        return ha_forecast

    @property
    def forecast(self) -> list[Forecast]:
        """Return the forecast array."""
        return self._forecast(self._hourly)

    @callback
    def _async_forecast_daily(self) -> list[Forecast]:
        """Return the daily forecast in native units."""
        return self._forecast(False)

    @callback
    def _async_forecast_hourly(self) -> list[Forecast]:
        """Return the hourly forecast in native units."""
        return self._forecast(True)

    @property
    def device_info(self):
        """Device info."""
        return DeviceInfo(
            name="Forecast",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN,)},
            manufacturer="Met Éireann",
            model="Forecast",
            configuration_url="https://www.met.ie",
        )
