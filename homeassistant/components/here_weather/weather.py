"""Support for the HERE Destination Weather API."""
import logging

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_SPEED,
    WeatherEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MODE, CONF_NAME, TEMP_CELSIUS
from homeassistant.core import HomeAssistant

from . import HEREWeatherData
from .const import CONDITION_CLASSES, DOMAIN, MODE_ASTRONOMY, MODE_DAILY_SIMPLE
from .utils import convert_unit_of_measurement_if_needed, get_attribute_from_here_data

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities
):
    """Add here_weather entities from a config_entry."""
    if config_entry.data[CONF_MODE] != MODE_ASTRONOMY:
        here_weather_data = hass.data[DOMAIN][config_entry.entry_id]

        async_add_entities(
            [
                HEREDestinationWeather(
                    config_entry.data[CONF_NAME],
                    here_weather_data,
                    config_entry.data[CONF_MODE],
                )
            ],
            True,
        )


class HEREDestinationWeather(WeatherEntity):
    """Implementation of an HERE Destination Weather WeatherEntity."""

    def __init__(self, name: str, here_data: HEREWeatherData, mode: str):
        """Initialize the sensor."""
        self._name = name
        self._here_data = here_data
        self._mode = mode

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Set unique_id for sensor."""
        return self._name

    @property
    def condition(self):
        """Return the current condition."""
        return get_condition_from_here_data(self._here_data.coordinator.data)

    @property
    def temperature(self) -> float:
        """Return the temperature."""
        return get_temperature_from_here_data(
            self._here_data.coordinator.data, self._mode
        )

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        try:
            return convert_unit_of_measurement_if_needed(
                self._here_data.units, TEMP_CELSIUS
            )
        except KeyError:
            return None

    @property
    def pressure(self):
        """Return the pressure."""
        return None

    @property
    def humidity(self):
        """Return the humidity."""
        get_attribute_from_here_data(self._here_data.coordinator.data, "humidity")

    @property
    def wind_speed(self):
        """Return the wind speed."""
        get_attribute_from_here_data(self._here_data.coordinator.data, "windSpeed")

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        get_attribute_from_here_data(self._here_data.coordinator.data, "windDirection")

    @property
    def attribution(self):
        """Return the attribution."""
        return None

    @property
    def forecast(self):
        """Return the forecast array."""
        if self._here_data.coordinator.data is None:
            return None
        data = []
        for offset in range(len(self._here_data.coordinator.data)):
            data.append(
                {
                    ATTR_FORECAST_TIME: get_attribute_from_here_data(
                        self._here_data.coordinator.data, "utcTime", offset
                    ),
                    ATTR_FORECAST_TEMP: get_high_or_default_temperature_from_here_data(
                        self._here_data.coordinator.data, self._mode, offset
                    ),
                    ATTR_FORECAST_TEMP_LOW: get_low_or_default_temperature_from_here_data(
                        self._here_data.coordinator.data, self._mode, offset
                    ),
                    ATTR_FORECAST_PRECIPITATION: calc_precipitation(
                        self._here_data.coordinator.data, offset
                    ),
                    ATTR_FORECAST_WIND_SPEED: get_attribute_from_here_data(
                        self._here_data.coordinator.data, "windSpeed", offset
                    ),
                    ATTR_FORECAST_WIND_BEARING: get_attribute_from_here_data(
                        self._here_data.coordinator.data, "windDirection", offset
                    ),
                    ATTR_FORECAST_CONDITION: get_condition_from_here_data(
                        self._here_data.coordinator.data, offset
                    ),
                }
            )
        return data

    @property
    def available(self):
        """Could the api be accessed during the last update call."""
        return self._here_data.coordinator.last_update_success

    @property
    def should_poll(self):
        """Return the polling requirement for this sensor."""
        return False

    @property
    def entity_registry_enabled_default(self):
        """Return if the entity should be enabled when first added to the entity registry."""
        return True

    @property
    def device_info(self) -> dict:
        """Return a device description for device registry."""

        return {
            "identifiers": {(DOMAIN, self._name)},
            "name": self._name,
            "manufacturer": "here.com",
        }

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self._here_data.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """Get the latest data from HERE."""
        await self._here_data.coordinator.async_request_refresh()


def get_condition_from_here_data(here_data: list, offset: int = 0) -> str:
    """Return the condition from here_data."""
    try:
        return [
            k
            for k, v in CONDITION_CLASSES.items()
            if get_attribute_from_here_data(here_data, "iconName", offset) in v
        ][0]
    except IndexError:
        return None


def get_high_or_default_temperature_from_here_data(
    here_data: list, mode: str, offset: int = 0
) -> str:
    """Return the temperature from here_data."""
    temperature = get_attribute_from_here_data(here_data, "highTemperature", offset)
    if temperature is not None:
        return float(temperature)

    return get_temperature_from_here_data(here_data, mode, offset)


def get_low_or_default_temperature_from_here_data(
    here_data: list, mode: str, offset: int = 0
) -> str:
    """Return the temperature from here_data."""
    temperature = get_attribute_from_here_data(here_data, "lowTemperature", offset)
    if temperature is not None:
        return float(temperature)
    return get_temperature_from_here_data(here_data, mode, offset)


def get_temperature_from_here_data(here_data: list, mode: str, offset: int = 0) -> str:
    """Return the temperature from here_data."""
    if mode == MODE_DAILY_SIMPLE:
        temperature = get_attribute_from_here_data(here_data, "highTemperature", offset)
    else:
        temperature = get_attribute_from_here_data(here_data, "temperature", offset)
    if temperature is not None:
        return float(temperature)


def calc_precipitation(here_data: list, offset: int = 0) -> float:
    """Calculate Precipitation."""
    rain_fall = get_attribute_from_here_data(here_data, "rainFall", offset)
    snow_fall = get_attribute_from_here_data(here_data, "snowFall", offset)
    if rain_fall is not None and snow_fall is not None:
        return float(rain_fall) + float(snow_fall)
