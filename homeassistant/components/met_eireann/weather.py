"""Support for Met Éireann weather service."""
import logging

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_TIME,
    WeatherEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    LENGTH_MILLIMETERS,
    PRESSURE_HPA,
    SPEED_METERS_PER_SECOND,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import ATTRIBUTION, CONDITION_MAP, DEFAULT_NAME, DOMAIN, FORECAST_MAP

_LOGGER = logging.getLogger(__name__)


def format_condition(condition: str):
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
    async_add_entities(
        [
            MetEireannWeather(coordinator, config_entry.data, False),
            MetEireannWeather(coordinator, config_entry.data, True),
        ]
    )


class MetEireannWeather(CoordinatorEntity, WeatherEntity):
    """Implementation of a Met Éireann weather condition."""

    _attr_native_precipitation_unit = LENGTH_MILLIMETERS
    _attr_native_pressure_unit = PRESSURE_HPA
    _attr_native_temperature_unit = TEMP_CELSIUS
    _attr_native_wind_speed_unit = SPEED_METERS_PER_SECOND

    def __init__(self, coordinator, config, hourly):
        """Initialise the platform with a data instance and site."""
        super().__init__(coordinator)
        self._config = config
        self._hourly = hourly

    @property
    def unique_id(self):
        """Return unique ID."""
        name_appendix = ""
        if self._hourly:
            name_appendix = "-hourly"

        return f"{self._config[CONF_LATITUDE]}-{self._config[CONF_LONGITUDE]}{name_appendix}"

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

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def forecast(self):
        """Return the forecast array."""
        if self._hourly:
            me_forecast = self.coordinator.data.hourly_forecast
        else:
            me_forecast = self.coordinator.data.daily_forecast
        required_keys = {"temperature", "datetime"}

        ha_forecast = []

        for item in me_forecast:
            if not set(item).issuperset(required_keys):
                continue
            ha_item = {
                k: item[v] for k, v in FORECAST_MAP.items() if item.get(v) is not None
            }
            if ha_item.get(ATTR_FORECAST_CONDITION):
                ha_item[ATTR_FORECAST_CONDITION] = format_condition(
                    ha_item[ATTR_FORECAST_CONDITION]
                )
            # Convert timestamp to UTC
            if ha_item.get(ATTR_FORECAST_TIME):
                ha_item[ATTR_FORECAST_TIME] = dt_util.as_utc(
                    ha_item.get(ATTR_FORECAST_TIME)
                ).isoformat()
            ha_forecast.append(ha_item)
        return ha_forecast

    @property
    def device_info(self):
        """Device info."""
        return DeviceInfo(
            default_name="Forecast",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN,)},
            manufacturer="Met Éireann",
            model="Forecast",
            configuration_url="https://www.met.ie",
        )
