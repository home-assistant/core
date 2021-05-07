"""Support for KNX/IP weather station."""
from __future__ import annotations

from xknx.devices import Weather as XknxWeather

from homeassistant.components.weather import WeatherEntity
from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN
from .knx_entity import KnxEntity


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up weather entities for KNX platform."""
    entities = []
    for device in hass.data[DOMAIN].xknx.devices:
        if isinstance(device, XknxWeather):
            entities.append(KNXWeather(device))
    async_add_entities(entities)


class KNXWeather(KnxEntity, WeatherEntity):
    """Representation of a KNX weather device."""

    def __init__(self, device: XknxWeather) -> None:
        """Initialize of a KNX sensor."""
        self._device: XknxWeather
        super().__init__(device)
        self._unique_id = f"{self._device._temperature.group_address_state}"

    @property
    def temperature(self) -> float | None:
        """Return current temperature."""
        return self._device.temperature

    @property
    def temperature_unit(self) -> str:
        """Return temperature unit."""
        return TEMP_CELSIUS

    @property
    def pressure(self) -> float | None:
        """Return current air pressure."""
        # KNX returns pA - HA requires hPa
        return (
            self._device.air_pressure / 100
            if self._device.air_pressure is not None
            else None
        )

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
    def wind_speed(self) -> float | None:
        """Return current wind speed in km/h."""
        # KNX only supports wind speed in m/s
        return (
            self._device.wind_speed * 3.6
            if self._device.wind_speed is not None
            else None
        )
