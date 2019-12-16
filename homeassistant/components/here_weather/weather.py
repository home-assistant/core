"""Support for the HERE Destination Weather API."""
import logging
from typing import Callable, Dict, Union

import herepy
import voluptuous as vol

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_SPEED,
    PLATFORM_SCHEMA,
    WeatherEntity,
)
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MODE,
    CONF_NAME,
    CONF_UNIT_SYSTEM,
    CONF_UNIT_SYSTEM_IMPERIAL,
    CONF_UNIT_SYSTEM_METRIC,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from . import (
    HEREWeatherData,
    convert_unit_of_measurement_if_needed,
    get_attribute_from_here_data,
)
from .const import (
    CONDITION_CLASSES,
    CONF_API_KEY,
    CONF_LOCATION_NAME,
    CONF_ZIP_CODE,
    DEFAULT_MODE,
    MODE_DAILY,
    MODE_DAILY_SIMPLE,
    MODE_HOURLY,
    MODE_OBSERVATION,
)

CONF_MODES = [MODE_HOURLY, MODE_DAILY, MODE_DAILY_SIMPLE, MODE_OBSERVATION]

UNITS = [CONF_UNIT_SYSTEM_METRIC, CONF_UNIT_SYSTEM_IMPERIAL]

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "HERE"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Inclusive(CONF_LATITUDE, "coordinates"): cv.latitude,
        vol.Inclusive(CONF_LONGITUDE, "coordinates"): cv.longitude,
        vol.Exclusive(CONF_LATITUDE, "coords_or_name_or_zip_code"): cv.latitude,
        vol.Exclusive(CONF_LOCATION_NAME, "coords_or_name_or_zip_code"): cv.string,
        vol.Exclusive(CONF_ZIP_CODE, "coords_or_name_or_zip_code"): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MODE, default=DEFAULT_MODE): vol.In(CONF_MODES),
        vol.Optional(CONF_LATITUDE): cv.latitude,
        vol.Optional(CONF_LONGITUDE): cv.longitude,
        vol.Optional(CONF_LOCATION_NAME): cv.string,
        vol.Optional(CONF_ZIP_CODE): cv.string,
        vol.Optional(CONF_UNIT_SYSTEM): vol.In(UNITS),
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: Dict[str, Union[str, bool]],
    async_add_entities: Callable,
    discovery_info: None = None,
) -> None:
    """Set up the HERE Destination weather platform."""

    api_key = config[CONF_API_KEY]

    here_client = herepy.DestinationWeatherApi(api_key)

    if not await hass.async_add_executor_job(
        _are_valid_client_credentials, here_client
    ):
        _LOGGER.error(
            "Invalid credentials. This error is returned if the specified token was invalid or no contract could be found for this token."
        )
        return

    name = config.get(CONF_NAME)
    mode = config[CONF_MODE]
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    location_name = config.get(CONF_LOCATION_NAME)
    zip_code = config.get(CONF_ZIP_CODE)
    units = config.get(CONF_UNIT_SYSTEM, hass.config.units.name)

    here_data = HEREWeatherData(
        here_client, mode, units, latitude, longitude, location_name, zip_code
    )

    async_add_entities([HEREDestinationWeather(name, here_data, mode)], True)


def _are_valid_client_credentials(here_client: herepy.DestinationWeatherApi) -> bool:
    """Check if the provided credentials are correct using defaults."""
    try:
        product = herepy.WeatherProductType.forecast_astronomy
        known_good_zip_code = "10025"
        here_client.weather_for_zip_code(known_good_zip_code, product)
    except herepy.UnauthorizedError:
        return False
    return True


class HEREDestinationWeather(WeatherEntity):
    """Implementation of an HERE Destination Weather WeatherEntity."""

    def __init__(self, name, here_data, mode):
        """Initialize the sensor."""
        self._name = name
        self._here_data = here_data
        self._mode = mode

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def condition(self):
        """Return the current condition."""
        return get_condition_from_here_data(self._here_data.data)

    @property
    def temperature(self) -> float:
        """Return the temperature."""
        return get_temperature_from_here_data(self._here_data.data)

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
        get_attribute_from_here_data(self._here_data.data, "humidity")

    @property
    def wind_speed(self):
        """Return the wind speed."""
        get_attribute_from_here_data(self._here_data.data, "windSpeed")

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        get_attribute_from_here_data(self._here_data.data, "windDirection")

    @property
    def attribution(self):
        """Return the attribution."""
        return None

    @property
    def forecast(self):
        """Return the forecast array."""
        if self._here_data.data is None:
            return None
        data = []
        for offset in range(len(self._here_data.data)):
            data.append(
                {
                    ATTR_FORECAST_TIME: get_attribute_from_here_data(
                        self._here_data.data, "utcTime", offset
                    ),
                    ATTR_FORECAST_TEMP: get_high_or_default_temperature_from_here_data(
                        self._here_data.data, offset
                    ),
                    ATTR_FORECAST_TEMP_LOW: get_low_or_default_temperature_from_here_data(
                        self._here_data.data, offset
                    ),
                    ATTR_FORECAST_PRECIPITATION: calc_precipitation(
                        self._here_data.data, offset
                    ),
                    ATTR_FORECAST_WIND_SPEED: get_attribute_from_here_data(
                        self._here_data.data, "windSpeed", offset
                    ),
                    ATTR_FORECAST_WIND_BEARING: get_attribute_from_here_data(
                        self._here_data.data, "windDirection", offset
                    ),
                    ATTR_FORECAST_CONDITION: get_condition_from_here_data(
                        self._here_data.data, offset
                    ),
                }
            )
        return data

    async def async_update(self) -> None:
        """Get the latest data from HERE."""
        await self.hass.async_add_executor_job(self._here_data.update)


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
    here_data: list, offset: int = 0
) -> str:
    """Return the temperature from here_data."""
    temperature = get_attribute_from_here_data(here_data, "highTemperature", offset)
    if temperature is not None:
        return float(temperature)

    return get_temperature_from_here_data(here_data, offset)


def get_low_or_default_temperature_from_here_data(
    here_data: list, offset: int = 0
) -> str:
    """Return the temperature from here_data."""
    temperature = get_attribute_from_here_data(here_data, "lowTemperature", offset)
    if temperature is not None:
        return float(temperature)
    return get_temperature_from_here_data(here_data, offset)


def get_temperature_from_here_data(here_data: list, offset: int = 0) -> str:
    """Return the temperature from here_data."""
    temperature = get_attribute_from_here_data(here_data, "temperature", offset)
    if temperature is not None:
        return float(temperature)


def calc_precipitation(here_data: list, offset: int = 0) -> float:
    """Calculate Precipitation."""
    rain_fall = get_attribute_from_here_data(here_data, "rainFall", offset)
    snow_fall = get_attribute_from_here_data(here_data, "snowFall", offset)
    if rain_fall is not None and snow_fall is not None:
        return float(rain_fall) + float(snow_fall)
