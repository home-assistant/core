"""Support for Met Éireann weather service."""
import logging

import voluptuous as vol

from homeassistant.components.weather import PLATFORM_SCHEMA, WeatherEntity
from homeassistant.const import (
    CONF_ELEVATION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    LENGTH_METERS,
    LENGTH_MILES,
    PRESSURE_HPA,
    PRESSURE_INHG,
    TEMP_CELSIUS,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.distance import convert as convert_distance
from homeassistant.util.pressure import convert as convert_pressure

from .const import ATTRIBUTION, CONDITION_MAP, CONF_TRACK_HOME, DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Inclusive(
            CONF_LATITUDE, "coordinates", "Latitude and longitude must exist together"
        ): cv.latitude,
        vol.Inclusive(
            CONF_LONGITUDE, "coordinates", "Latitude and longitude must exist together"
        ): cv.longitude,
        vol.Optional(CONF_ELEVATION): int,
    }
)


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
        self._name_appendix = "-hourly" if hourly else ""

    @property
    def track_home(self):
        """Return if we are tracking home."""
        return self._config.get(CONF_TRACK_HOME, False)

    @property
    def unique_id(self):
        """Return unique ID."""
        if self.track_home:
            return f"home{self._name_appendix}"

        return f"{self._config[CONF_LATITUDE]}-{self._config[CONF_LONGITUDE]}{self._name_appendix}"

    @property
    def name(self):
        """Return the name of the sensor."""
        name = self._config.get(CONF_NAME)

        if name is not None:
            return f"{name}{self._name_appendix}"

        if self.track_home:
            return f"{self.hass.config.location_name}{self._name_appendix}"

        return f"{DEFAULT_NAME}{self._name_appendix}"

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
            # Format the condition for hourly forecast items
            for item in self.coordinator.data.hourly_forecast:
                if "condition" in item:
                    item["condition"] = format_condition(item["condition"])
            return self.coordinator.data.hourly_forecast
        # Format the condition for daily forecast items
        for item in self.coordinator.data.daily_forecast:
            if "condition" in item:
                item["condition"] = format_condition(item["condition"])
        return self.coordinator.data.daily_forecast
