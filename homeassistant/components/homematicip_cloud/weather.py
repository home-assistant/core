"""Support for HomematicIP Cloud weather devices."""
from homematicip.aio.device import (
    AsyncWeatherSensor,
    AsyncWeatherSensorPlus,
    AsyncWeatherSensorPro,
)
from homematicip.base.enums import WeatherCondition

from homeassistant.components.weather import WeatherEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.typing import HomeAssistantType

from . import DOMAIN as HMIPC_DOMAIN, HomematicipGenericEntity
from .hap import HomematicipHAP

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


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the HomematicIP weather sensor from a config entry."""
    hap = hass.data[HMIPC_DOMAIN][config_entry.unique_id]
    entities = []
    for device in hap.home.devices:
        if isinstance(device, AsyncWeatherSensorPro):
            entities.append(HomematicipWeatherSensorPro(hap, device))
        elif isinstance(device, (AsyncWeatherSensor, AsyncWeatherSensorPlus)):
            entities.append(HomematicipWeatherSensor(hap, device))

    entities.append(HomematicipHomeWeather(hap))

    if entities:
        async_add_entities(entities)


class HomematicipWeatherSensor(HomematicipGenericEntity, WeatherEntity):
    """Representation of the HomematicIP weather sensor plus & basic."""

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize the weather sensor."""
        super().__init__(hap, device)

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
    """Representation of the HomematicIP weather sensor pro."""

    @property
    def wind_bearing(self) -> float:
        """Return the wind bearing."""
        return self._device.windDirection


class HomematicipHomeWeather(HomematicipGenericEntity, WeatherEntity):
    """Representation of the HomematicIP home weather."""

    def __init__(self, hap: HomematicipHAP) -> None:
        """Initialize the home weather."""
        hap.home.modelType = "HmIP-Home-Weather"
        super().__init__(hap, hap.home)

    @property
    def available(self) -> bool:
        """Return if weather entity is available."""
        return self._home.connected

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"Weather {self._home.location.city}"

    @property
    def temperature(self) -> float:
        """Return the temperature."""
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
