"""Support for KNX/IP weather station."""

from __future__ import annotations

from xknx import XKNX
from xknx.devices import Weather as XknxWeather

from homeassistant import config_entries
from homeassistant.components.weather import WeatherEntity
from homeassistant.const import (
    CONF_ENTITY_CATEGORY,
    CONF_NAME,
    Platform,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .const import DATA_KNX_CONFIG, DOMAIN
from .knx_entity import KnxEntity
from .schema import WeatherSchema


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch(es) for KNX platform."""
    xknx: XKNX = hass.data[DOMAIN].xknx
    config: list[ConfigType] = hass.data[DATA_KNX_CONFIG][Platform.WEATHER]

    async_add_entities(KNXWeather(xknx, entity_config) for entity_config in config)


def _create_weather(xknx: XKNX, config: ConfigType) -> XknxWeather:
    """Return a KNX weather device to be used within XKNX."""
    return XknxWeather(
        xknx,
        name=config[CONF_NAME],
        sync_state=config[WeatherSchema.CONF_SYNC_STATE],
        group_address_temperature=config[WeatherSchema.CONF_KNX_TEMPERATURE_ADDRESS],
        group_address_brightness_south=config.get(
            WeatherSchema.CONF_KNX_BRIGHTNESS_SOUTH_ADDRESS
        ),
        group_address_brightness_east=config.get(
            WeatherSchema.CONF_KNX_BRIGHTNESS_EAST_ADDRESS
        ),
        group_address_brightness_west=config.get(
            WeatherSchema.CONF_KNX_BRIGHTNESS_WEST_ADDRESS
        ),
        group_address_brightness_north=config.get(
            WeatherSchema.CONF_KNX_BRIGHTNESS_NORTH_ADDRESS
        ),
        group_address_wind_speed=config.get(WeatherSchema.CONF_KNX_WIND_SPEED_ADDRESS),
        group_address_wind_bearing=config.get(
            WeatherSchema.CONF_KNX_WIND_BEARING_ADDRESS
        ),
        group_address_rain_alarm=config.get(WeatherSchema.CONF_KNX_RAIN_ALARM_ADDRESS),
        group_address_frost_alarm=config.get(
            WeatherSchema.CONF_KNX_FROST_ALARM_ADDRESS
        ),
        group_address_wind_alarm=config.get(WeatherSchema.CONF_KNX_WIND_ALARM_ADDRESS),
        group_address_day_night=config.get(WeatherSchema.CONF_KNX_DAY_NIGHT_ADDRESS),
        group_address_air_pressure=config.get(
            WeatherSchema.CONF_KNX_AIR_PRESSURE_ADDRESS
        ),
        group_address_humidity=config.get(WeatherSchema.CONF_KNX_HUMIDITY_ADDRESS),
    )


class KNXWeather(KnxEntity, WeatherEntity):
    """Representation of a KNX weather device."""

    _device: XknxWeather
    _attr_native_pressure_unit = UnitOfPressure.PA
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND

    def __init__(self, xknx: XKNX, config: ConfigType) -> None:
        """Initialize of a KNX sensor."""
        super().__init__(_create_weather(xknx, config))
        self._attr_unique_id = str(self._device._temperature.group_address_state)
        self._attr_entity_category = config.get(CONF_ENTITY_CATEGORY)

    @property
    def native_temperature(self) -> float | None:
        """Return current temperature in C."""
        return self._device.temperature

    @property
    def native_pressure(self) -> float | None:
        """Return current air pressure in Pa."""
        return self._device.air_pressure

    @property
    def condition(self) -> str:
        """Return current weather condition."""
        return self._device.ha_current_state().value

    @property
    def humidity(self) -> float | None:
        """Return current humidity."""
        return self._device.humidity

    @property
    def wind_bearing(self) -> int | None:
        """Return current wind bearing in degrees."""
        return self._device.wind_bearing

    @property
    def native_wind_speed(self) -> float | None:
        """Return current wind speed in m/s."""
        return self._device.wind_speed
