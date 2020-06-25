"""Support for Meteoclimatic weather service."""
import logging

from meteoclimatic import Condition

from homeassistant.components.weather import WeatherEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import callback
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    ATTRIBUTION,
    CONDITION_CLASSES,
    DOMAIN,
    METEOCLIMATIC_COORDINATOR,
    METEOCLIMATIC_STATION_CODE,
    METEOCLIMATIC_STATION_NAME,
    METEOCLIMATIC_UPDATER,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the Meteoclimatic weather platform."""
    hass_data = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([MeteoclimaticWeather(hass_data)], True)


class MeteoclimaticWeather(WeatherEntity):
    """Representation of a weather condition."""

    def __init__(self, hass_data: dict):
        """Initialise the weather platform."""
        self._updater = hass_data[METEOCLIMATIC_UPDATER]
        self._coordinator = hass_data[METEOCLIMATIC_COORDINATOR]
        self._name = hass_data[METEOCLIMATIC_STATION_NAME]
        self._unique_id = hass_data[METEOCLIMATIC_STATION_CODE]

        self._data = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        return self._unique_id

    @property
    def condition(self):
        """Return the current condition."""
        return (
            self.format_condition(self._data.weather.condition)
            if self._data is not None and hasattr(self._data, "weather")
            else None
        )

    @property
    def temperature(self):
        """Return the temperature."""
        return (
            self._data.weather.temp_current
            if self._data is not None and hasattr(self._data, "weather")
            else None
        )

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def humidity(self):
        """Return the humidity."""
        return (
            self._data.weather.humidity_current
            if self._data is not None and hasattr(self._data, "weather")
            else None
        )

    @property
    def pressure(self):
        """Return the pressure."""
        return (
            self._data.weather.pressure_current
            if self._data is not None and hasattr(self._data, "weather")
            else None
        )

    @property
    def wind_speed(self):
        """Return the wind speed."""
        return (
            self._data.weather.wind_current
            if self._data is not None and hasattr(self._data, "weather")
            else None
        )

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        return (
            self._data.weather.wind_bearing
            if self._data is not None and hasattr(self._data, "weather")
            else None
        )

    @staticmethod
    def format_condition(condition):
        """Return condition from dict CONDITION_CLASSES."""
        for key, value in CONDITION_CLASSES.items():
            if condition in value:
                return key
        if isinstance(condition, Condition):
            return condition.value
        return condition

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    async def async_added_to_hass(self) -> None:
        """Set up a listener and load data."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self._update_callback)
        )
        self._update_callback()

    @callback
    def _update_callback(self) -> None:
        """Load data from integration."""
        self._data = self._updater.get_data()
        self.async_write_ha_state()

    @property
    def should_poll(self) -> bool:
        """Entities do not individually poll."""
        return False

    @property
    def available(self):
        """Return if state is available."""
        return self._data is not None
