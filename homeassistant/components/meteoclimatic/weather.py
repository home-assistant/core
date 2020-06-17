"""Support for Meteoclimatic weather service."""
import logging

from meteoclimatic import Condition

from homeassistant.components.weather import WeatherEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.typing import HomeAssistantType

from . import MeteoclimaticUpdater
from .const import ATTRIBUTION, CONDITION_CLASSES, CONF_STATION_CODE, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the Meteoclimatic weather platform."""
    station_code = entry.data[CONF_STATION_CODE]
    updater = hass.data[DOMAIN][station_code]

    async_add_entities([MeteoclimaticWeather(updater)], True)


class MeteoclimaticWeather(WeatherEntity):
    """Representation of a weather condition."""

    def __init__(self, updater: MeteoclimaticUpdater):
        """Initialise the weather platform."""
        self._updater = updater
        self._data = None

    def update(self):
        """Update current conditions."""
        self._updater.update()
        self._data = self._updater.get_data()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._data.station.name

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        return self._data.station.code

    @property
    def condition(self):
        """Return the current condition."""
        return self.format_condition(self._data.weather.condition)

    @property
    def temperature(self):
        """Return the temperature."""
        return self._data.weather.temp_current

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def humidity(self):
        """Return the humidity."""
        return self._data.weather.humidity_current

    @property
    def pressure(self):
        """Return the pressure."""
        return self._data.weather.pressure_current

    @property
    def wind_speed(self):
        """Return the wind speed."""
        return self._data.weather.wind_current

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        return self._data.weather.wind_bearing

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @staticmethod
    def format_condition(condition):
        """Return condition from dict CONDITION_CLASSES."""
        for key, value in CONDITION_CLASSES.items():
            if condition in value:
                return key
        if isinstance(condition, Condition):
            return condition.value
        return condition
