"""Support for Meteo-France weather service."""
from datetime import timedelta
import logging

from meteofrance.client import meteofranceClient

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
    WeatherEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.typing import HomeAssistantType
import homeassistant.util.dt as dt_util

from .const import ATTRIBUTION, CONDITION_CLASSES, CONF_CITY, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the Meteo-France weather platform."""
    city = entry.data[CONF_CITY]
    client = hass.data[DOMAIN][city]

    async_add_entities([MeteoFranceWeather(client)], True)


class MeteoFranceWeather(WeatherEntity):
    """Representation of a weather condition."""

    def __init__(self, client: meteofranceClient):
        """Initialise the platform with a data instance and station name."""
        self._client = client
        self._data = {}

    def update(self):
        """Update current conditions."""
        self._client.update()
        self._data = self._client.get_data()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._data["name"]

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        return self.name

    @property
    def condition(self):
        """Return the current condition."""
        return self.format_condition(self._data["weather"])

    @property
    def temperature(self):
        """Return the temperature."""
        return self._data["temperature"]

    @property
    def humidity(self):
        """Return the humidity."""
        return None

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def wind_speed(self):
        """Return the wind speed."""
        return self._data["wind_speed"]

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        return self._data["wind_bearing"]

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def forecast(self):
        """Return the forecast."""
        reftime = dt_util.utcnow().replace(hour=12, minute=0, second=0, microsecond=0)
        reftime += timedelta(hours=24)
        _LOGGER.debug("reftime used for %s forecast: %s", self._data["name"], reftime)
        forecast_data = []
        for key in self._data["forecast"]:
            value = self._data["forecast"][key]
            data_dict = {
                ATTR_FORECAST_TIME: reftime.isoformat(),
                ATTR_FORECAST_TEMP: int(value["max_temp"]),
                ATTR_FORECAST_TEMP_LOW: int(value["min_temp"]),
                ATTR_FORECAST_CONDITION: self.format_condition(value["weather"]),
            }
            reftime = reftime + timedelta(hours=24)
            forecast_data.append(data_dict)
        return forecast_data

    @staticmethod
    def format_condition(condition):
        """Return condition from dict CONDITION_CLASSES."""
        for key, value in CONDITION_CLASSES.items():
            if condition in value:
                return key
        return condition

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        data = dict()
        if self._data and "next_rain" in self._data:
            data["next_rain"] = self._data["next_rain"]
        return data
