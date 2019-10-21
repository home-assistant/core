"""Support for HomematicIP Cloud weather devices."""
import logging

from homematicip.aio.device import (
    AsyncWeatherSensor,
    AsyncWeatherSensorPlus,
    AsyncWeatherSensorPro,
)
from homematicip.aio.home import AsyncHome
from homematicip.base.enums import WeatherCondition

from homeassistant.components.weather import WeatherEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import HomeAssistant

from . import DOMAIN as HMIPC_DOMAIN, HMIPC_HAPID, HomematicipGenericDevice

_LOGGER = logging.getLogger(__name__)

HOME_WEATHER_CONDITION = {
    WeatherCondition.CLEAR: "sunny",
    WeatherCondition.LIGHT_CLOUDY: "partlycloudy",
    WeatherCondition.CLOUDY: "cloudy",
    WeatherCondition.CLOUDY_WITH_RAIN: "rainy",
    WeatherCondition.CLOUDY_WITH_SNOW_RAIN: "snowy-rainy",
    WeatherCondition.HEAVILY_CLOUDY: "cloudy",
    WeatherCondition.HEAVILY_CLOUDY_WITH_RAIN: "rainy",
    WeatherCondition.HEAVILY_CLOUDY_WITH_STRONG_RAIN: "snowy-rainy",
    WeatherCondition.HEAVILY_CLOUDY_WITH_SNOW: "snowy",
    WeatherCondition.HEAVILY_CLOUDY_WITH_SNOW_RAIN: "snowy-rainy",
    WeatherCondition.HEAVILY_CLOUDY_WITH_THUNDER: "lightning",
    WeatherCondition.HEAVILY_CLOUDY_WITH_RAIN_AND_THUNDER: "lightning-rainy",
    WeatherCondition.FOGGY: "fog",
    WeatherCondition.STRONG_WIND: "windy",
    WeatherCondition.UNKNOWN: "",
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the HomematicIP Cloud weather sensor."""
    pass


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the HomematicIP weather sensor from a config entry."""
    home = hass.data[HMIPC_DOMAIN][config_entry.data[HMIPC_HAPID]].home
    devices = []
    for device in home.devices:
        if isinstance(device, AsyncWeatherSensorPro):
            devices.append(HomematicipWeatherSensorPro(home, device))
        elif isinstance(device, (AsyncWeatherSensor, AsyncWeatherSensorPlus)):
            devices.append(HomematicipWeatherSensor(home, device))

    devices.append(HomematicipHomeWeather(home))

    if devices:
        async_add_entities(devices)


class HomematicipWeatherSensor(HomematicipGenericDevice, WeatherEntity):
    """representation of a HomematicIP Cloud weather sensor plus & basic."""

    def __init__(self, home: AsyncHome, device) -> None:
        """Initialize the weather sensor."""
        super().__init__(home, device)

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._device.label

    @property
    def temperature(self) -> float:
        """Return the platform temperature."""
        return self._device.actualTemperature

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def humidity(self) -> int:
        """Return the humidity."""
        return self._device.humidity

    @property
    def wind_speed(self) -> float:
        """Return the wind speed."""
        return self._device.windSpeed

    @property
    def attribution(self) -> str:
        """Return the attribution."""
        return "Powered by Homematic IP"

    @property
    def condition(self) -> str:
        """Return the current condition."""
        if getattr(self._device, "raining", None):
            return "rainy"
        if self._device.storm:
            return "windy"
        if self._device.sunshine:
            return "sunny"
        return ""


class HomematicipWeatherSensorPro(HomematicipWeatherSensor):
    """representation of a HomematicIP weather sensor pro."""

    @property
    def wind_bearing(self) -> float:
        """Return the wind bearing."""
        return self._device.windDirection


class HomematicipHomeWeather(HomematicipGenericDevice, WeatherEntity):
    """representation of a HomematicIP Cloud home weather."""

    def __init__(self, home: AsyncHome) -> None:
        """Initialize the home weather."""
        home.weather.modelType = "HmIP-Home-Weather"
        super().__init__(home, home)

    @property
    def available(self) -> bool:
        """Device available."""
        return self._home.connected

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"Weather {self._home.location.city}"

    @property
    def temperature(self) -> float:
        """Return the platform temperature."""
        return self._device.weather.temperature

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def humidity(self) -> int:
        """Return the humidity."""
        return self._device.weather.humidity

    @property
    def wind_speed(self) -> float:
        """Return the wind speed."""
        return round(self._device.weather.windSpeed, 1)

    @property
    def wind_bearing(self) -> float:
        """Return the wind bearing."""
        return self._device.weather.windDirection

    @property
    def attribution(self) -> str:
        """Return the attribution."""
        return "Powered by Homematic IP"

    @property
    def condition(self) -> str:
        """Return the current condition."""
        return HOME_WEATHER_CONDITION.get(self._device.weather.weatherCondition)
