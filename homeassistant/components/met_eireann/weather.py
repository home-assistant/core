"""Support for Met Éireann weather service."""
import logging

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TIME,
    WeatherEntity,
)
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    LENGTH_INCHES,
    LENGTH_METERS,
    LENGTH_MILES,
    LENGTH_MILLIMETERS,
    PRESSURE_HPA,
    PRESSURE_INHG,
    TEMP_CELSIUS,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util
from homeassistant.util.distance import convert as convert_distance
from homeassistant.util.pressure import convert as convert_pressure

from .const import ATTRIBUTION, CONDITION_MAP, DEFAULT_NAME, DOMAIN, FORECAST_MAP

_LOGGER = logging.getLogger(__name__)


def format_condition(condition: str):
    """Map the conditions provided by the weather API to those supported by the frontend."""
    if condition is not None:
        for key, value in CONDITION_MAP.items():
            if condition in value:
                return key
    return condition


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add a weather entity from a config_entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [
            MetEireannWeather(
                coordinator, config_entry.data, hass.config.units.is_metric, False
            ),
            MetEireannWeather(
                coordinator, config_entry.data, hass.config.units.is_metric, True
            ),
        ]
    )


class MetEireannWeather(CoordinatorEntity, WeatherEntity):
    """Implementation of a Met Éireann weather condition."""

    def __init__(self, coordinator, config, is_metric, hourly):
        """Initialise the platform with a data instance and site."""
        super().__init__(coordinator)
        self._config = config
        self._is_metric = is_metric
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
    def temperature(self):
        """Return the temperature."""
        return self.coordinator.data.current_weather_data.get("temperature")

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def pressure(self):
        """Return the pressure."""
        pressure_hpa = self.coordinator.data.current_weather_data.get("pressure")
        if self._is_metric or pressure_hpa is None:
            return pressure_hpa

        return round(convert_pressure(pressure_hpa, PRESSURE_HPA, PRESSURE_INHG), 2)

    @property
    def humidity(self):
        """Return the humidity."""
        return self.coordinator.data.current_weather_data.get("humidity")

    @property
    def wind_speed(self):
        """Return the wind speed."""
        speed_m_s = self.coordinator.data.current_weather_data.get("wind_speed")
        if self._is_metric or speed_m_s is None:
            return speed_m_s

        speed_mi_s = convert_distance(speed_m_s, LENGTH_METERS, LENGTH_MILES)
        speed_mi_h = speed_mi_s / 3600.0
        return int(round(speed_mi_h))

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
        required_keys = {ATTR_FORECAST_TEMP, ATTR_FORECAST_TIME}

        ha_forecast = []

        for item in me_forecast:
            if not set(item).issuperset(required_keys):
                continue
            ha_item = {
                k: item[v] for k, v in FORECAST_MAP.items() if item.get(v) is not None
            }
            if not self._is_metric and ATTR_FORECAST_PRECIPITATION in ha_item:
                precip_inches = convert_distance(
                    ha_item[ATTR_FORECAST_PRECIPITATION],
                    LENGTH_MILLIMETERS,
                    LENGTH_INCHES,
                )
                ha_item[ATTR_FORECAST_PRECIPITATION] = round(precip_inches, 2)
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
        return {
            "identifiers": {(DOMAIN,)},
            "manufacturer": "Met Éireann",
            "model": "Forecast",
            "default_name": "Forecast",
            "entry_type": "service",
        }
