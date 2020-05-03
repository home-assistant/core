"""Support for UK Met Office weather service."""

import logging

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_SPEED,
    WeatherEntity,
)
from homeassistant.const import LENGTH_KILOMETERS, TEMP_CELSIUS
from homeassistant.core import callback
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import (
    ATTRIBUTION,
    CONDITION_CLASSES,
    DEFAULT_NAME,
    DOMAIN,
    METOFFICE_COORDINATOR,
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
        """Initialise the platform with a data instance."""
        self._data = hass_data[METOFFICE_DATA]
        self._coordinator = hass_data[METOFFICE_COORDINATOR]

        self._name = f"{DEFAULT_NAME} {hass_data[METOFFICE_NAME]}"
        self._unique_id = f"{self._data.latitude}_{self._data.longitude}"

        self.metoffice_now = None
        self.metoffice_all = None

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
                if self.metoffice_now.weather.value in v
            ][0]
            if self.metoffice_now
            else None
        )

    @property
    def temperature(self):
        """Return the platform temperature."""
        return (
            self.metoffice_now.temperature.value
            if self.metoffice_now and self.metoffice_now.temperature
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
        if hasattr(self.metoffice_now, "visibility"):
            _visibility = f"{VISIBILITY_CLASSES.get(self.metoffice_now.visibility.value)} - {VISIBILITY_DISTANCE_CLASSES.get(self.metoffice_now.visibility.value)}"
        return _visibility

    @property
    def visibility_unit(self):
        """Return the unit of measurement."""
        return LENGTH_KILOMETERS

    @property
    def pressure(self):
        """Return the mean sea-level pressure."""
        return (
            self.metoffice_now.pressure.value
            if self.metoffice_now and self.metoffice_now.pressure
            else None
        )

    @property
    def humidity(self):
        """Return the relative humidity."""
        return (
            self.metoffice_now.humidity.value
            if self.metoffice_now and self.metoffice_now.humidity
            else None
        )

    @property
    def wind_speed(self):
        """Return the wind speed."""
        return (
            self.metoffice_now.wind_speed.value
            if self.metoffice_now and self.metoffice_now.wind_speed
            else None
        )

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        return (
            self.metoffice_now.wind_direction.value
            if self.metoffice_now and self.metoffice_now.wind_direction
            else None
        )

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def forecast(self):
        """Return the forecast array."""
        data = [
            {
                ATTR_FORECAST_CONDITION: [
                    k
                    for k, v in CONDITION_CLASSES.items()
                    if timestep.weather.value in v
                ][0]
                if timestep.weather
                else None,
                ATTR_FORECAST_PRECIPITATION: timestep.precipitation.value
                if timestep.precipitation
                else None,
                ATTR_FORECAST_TEMP: timestep.temperature.value
                if timestep.temperature
                else None,
                ATTR_FORECAST_TIME: timestep.date,
                ATTR_FORECAST_WIND_BEARING: timestep.wind_direction.value
                if timestep.wind_direction
                else None,
                ATTR_FORECAST_WIND_SPEED: timestep.wind_speed.value
                if timestep.wind_speed
                else None,
            }
            for timestep in self.metoffice_all
        ]

        return data

    async def async_added_to_hass(self) -> None:
        """Set up a listener and load data."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self._update_callback)
        )
        self._update_callback()

    @callback
    def _update_callback(self) -> None:
        """Load data from integration."""
        self.metoffice_now = self._data.now
        self.metoffice_all = self._data.all
        self.async_write_ha_state()

    @property
    def should_poll(self) -> bool:
        """Entities do not individually poll."""
        return False

    @property
    def available(self):
        """Return if state is available."""
        return self.metoffice_now is not None and self.metoffice_all is not None
