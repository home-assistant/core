"""Support for HomematicIP Cloud weather devices."""

from __future__ import annotations

from homematicip.aio.device import (
    AsyncWeatherSensor,
    AsyncWeatherSensorPlus,
    AsyncWeatherSensorPro,
)
from homematicip.base.enums import WeatherCondition

from homeassistant.components.weather import (
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_LIGHTNING,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY,
    WeatherEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfSpeed, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN as HMIPC_DOMAIN, HomematicipGenericEntity
from .hap import HomematicipHAP

HOME_WEATHER_CONDITION = {
    WeatherCondition.CLEAR: ATTR_CONDITION_SUNNY,
    WeatherCondition.LIGHT_CLOUDY: ATTR_CONDITION_PARTLYCLOUDY,
    WeatherCondition.CLOUDY: ATTR_CONDITION_CLOUDY,
    WeatherCondition.CLOUDY_WITH_RAIN: ATTR_CONDITION_RAINY,
    WeatherCondition.CLOUDY_WITH_SNOW_RAIN: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCondition.HEAVILY_CLOUDY: ATTR_CONDITION_CLOUDY,
    WeatherCondition.HEAVILY_CLOUDY_WITH_RAIN: ATTR_CONDITION_RAINY,
    WeatherCondition.HEAVILY_CLOUDY_WITH_STRONG_RAIN: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCondition.HEAVILY_CLOUDY_WITH_SNOW: ATTR_CONDITION_SNOWY,
    WeatherCondition.HEAVILY_CLOUDY_WITH_SNOW_RAIN: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCondition.HEAVILY_CLOUDY_WITH_THUNDER: ATTR_CONDITION_LIGHTNING,
    WeatherCondition.HEAVILY_CLOUDY_WITH_RAIN_AND_THUNDER: ATTR_CONDITION_LIGHTNING_RAINY,
    WeatherCondition.FOGGY: ATTR_CONDITION_FOG,
    WeatherCondition.STRONG_WIND: ATTR_CONDITION_WINDY,
    WeatherCondition.UNKNOWN: "",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the HomematicIP weather sensor from a config entry."""
    hap = hass.data[HMIPC_DOMAIN][config_entry.unique_id]
    entities: list[HomematicipGenericEntity] = []
    for device in hap.home.devices:
        if isinstance(device, AsyncWeatherSensorPro):
            entities.append(HomematicipWeatherSensorPro(hap, device))
        elif isinstance(device, (AsyncWeatherSensor, AsyncWeatherSensorPlus)):
            entities.append(HomematicipWeatherSensor(hap, device))

    entities.append(HomematicipHomeWeather(hap))

    async_add_entities(entities)


class HomematicipWeatherSensor(HomematicipGenericEntity, WeatherEntity):
    """Representation of the HomematicIP weather sensor plus & basic."""

    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_attribution = "Powered by Homematic IP"

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize the weather sensor."""
        super().__init__(hap, device)

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._device.label

    @property
    def native_temperature(self) -> float:
        """Return the platform temperature."""
        return self._device.actualTemperature

    @property
    def humidity(self) -> int:
        """Return the humidity."""
        return self._device.humidity

    @property
    def native_wind_speed(self) -> float:
        """Return the wind speed."""
        return self._device.windSpeed

    @property
    def condition(self) -> str:
        """Return the current condition."""
        if getattr(self._device, "raining", None):
            return ATTR_CONDITION_RAINY
        if self._device.storm:
            return ATTR_CONDITION_WINDY
        if self._device.sunshine:
            return ATTR_CONDITION_SUNNY
        return ""


class HomematicipWeatherSensorPro(HomematicipWeatherSensor):
    """Representation of the HomematicIP weather sensor pro."""

    @property
    def wind_bearing(self) -> float:
        """Return the wind bearing."""
        return self._device.windDirection


class HomematicipHomeWeather(HomematicipGenericEntity, WeatherEntity):
    """Representation of the HomematicIP home weather."""

    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_attribution = "Powered by Homematic IP"

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
    def native_temperature(self) -> float:
        """Return the temperature."""
        return self._device.weather.temperature

    @property
    def humidity(self) -> int:
        """Return the humidity."""
        return self._device.weather.humidity

    @property
    def native_wind_speed(self) -> float:
        """Return the wind speed."""
        return round(self._device.weather.windSpeed, 1)

    @property
    def wind_bearing(self) -> float:
        """Return the wind bearing."""
        return self._device.weather.windDirection

    @property
    def condition(self) -> str | None:
        """Return the current condition."""
        return HOME_WEATHER_CONDITION.get(self._device.weather.weatherCondition)
