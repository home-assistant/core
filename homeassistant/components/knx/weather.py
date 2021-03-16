"""Support for KNX/IP weather station."""
from typing import Callable, Optional

from xknx.devices import Weather as XknxWeather

from homeassistant.components.weather import WeatherEntity
from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.typing import (
    ConfigType,
    DiscoveryInfoType,
    HomeAssistantType,
)

from .const import DOMAIN
from .knx_entity import KnxEntity


async def async_setup_platform(
    hass: HomeAssistantType,
    config: ConfigType,
    async_add_entities: Callable,
    discovery_info: Optional[DiscoveryInfoType] = None,
) -> None:
    """Set up weather entities for KNX platform."""
    entities = []
    for device in hass.data[DOMAIN].xknx.devices:
        if isinstance(device, XknxWeather):
            entities.append(KNXWeather(device))
    async_add_entities(entities)


class KNXWeather(KnxEntity, WeatherEntity):
    """Representation of a KNX weather device."""

    def __init__(self, device: XknxWeather):
        """Initialize of a KNX sensor."""
        self._device: XknxWeather
        super().__init__(device)

    @property
    def temperature(self) -> Optional[float]:
        """Return current temperature."""
        return self._device.temperature

    @property
    def temperature_unit(self) -> str:
        """Return temperature unit."""
        return TEMP_CELSIUS

    @property
    def pressure(self) -> Optional[float]:
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
    def humidity(self) -> Optional[float]:
        """Return current humidity."""
        return self._device.humidity

    @property
    def wind_bearing(self) -> Optional[int]:
        """Return current wind bearing in degrees."""
        return self._device.wind_bearing

    @property
    def wind_speed(self) -> Optional[float]:
        """Return current wind speed in km/h."""
        # KNX only supports wind speed in m/s
        return (
            self._device.wind_speed * 3.6
            if self._device.wind_speed is not None
            else None
        )
