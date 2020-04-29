"""Support for UK Met Office weather service."""

import logging

from homeassistant.components.weather import WeatherEntity
from homeassistant.const import LENGTH_KILOMETERS, TEMP_CELSIUS
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import (
    ATTRIBUTION,
    CONDITION_CLASSES,
    DEFAULT_NAME,
    DOMAIN,
    METOFFICE_DATA,
    METOFFICE_NAME,
    VISIBILITY_CLASSES,
    VISIBILITY_DISTANCE_CLASSES,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigType, async_add_entities
) -> None:
    """Set up the Met Office weather sensor platform."""
    hass_data = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [MetOfficeWeather(entry.data, hass_data,)], False,
    )


class MetOfficeWeather(WeatherEntity):
    """Implementation of a Met Office weather condition."""

    def __init__(self, entry_data, hass_data):
        """Initialise the platform with a data instance and site."""
        self._data = hass_data[METOFFICE_DATA]
        self._name = f"{DEFAULT_NAME} {hass_data[METOFFICE_NAME]}"
        self._unique_id = f"{DOMAIN}_{self._data.latitude}_{self._data.longitude}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique of the sensor."""
        return self._unique_id

    @property
    def condition(self):
        """Return the current condition."""
        return (
            [
                k
                for k, v in CONDITION_CLASSES.items()
                if self._data.now.weather.value in v
            ][0]
            if self._data.now
            else None
        )

    @property
    def temperature(self):
        """Return the platform temperature."""
        return (
            self._data.now.temperature.value
            if self._data.now and self._data.now.temperature
            else None
        )

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def visibility(self):
        """Return the platform visibility."""
        _visibility = None
        if hasattr(self._data.now, "visibility"):
            _visibility = f"{VISIBILITY_CLASSES.get(self._data.now.visibility.value)} - {VISIBILITY_DISTANCE_CLASSES.get(self._data.now.visibility.value)}"
        return _visibility

    @property
    def visibility_unit(self):
        """Return the unit of measurement."""
        return LENGTH_KILOMETERS

    @property
    def pressure(self):
        """Return the mean sea-level pressure."""
        return (
            self._data.now.pressure.value
            if self._data.now and self._data.now.pressure
            else None
        )

    @property
    def humidity(self):
        """Return the relative humidity."""
        return (
            self._data.now.humidity.value
            if self._data.now and self._data.now.humidity
            else None
        )

    @property
    def wind_speed(self):
        """Return the wind speed."""
        return (
            self._data.now.wind_speed.value
            if self._data.now and self._data.now.wind_speed
            else None
        )

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        return (
            self._data.now.wind_direction.value
            if self._data.now and self._data.now.wind_direction
            else None
        )

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    def update(self):
        """Update current conditions."""
        self._data.update()
