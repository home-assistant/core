"""Support for KNX/IP weather station."""
from typing import Any, Dict, Optional

from xknx.devices import Weather as XknxWeather

from homeassistant.components.weather import WeatherEntity
from homeassistant.const import TEMP_CELSIUS

from .const import (
    ATTR_BRIGHTNESS_EAST,
    ATTR_BRIGHTNESS_NORTH,
    ATTR_BRIGHTNESS_SOUTH,
    ATTR_BRIGHTNESS_WEST,
    ATTR_FROST_ALARM,
    ATTR_RAIN_ALARM,
    ATTR_WIND_ALARM,
    DATA_KNX,
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the scenes for KNX platform."""
    entities = []
    for device in hass.data[DATA_KNX].xknx.devices:
        if isinstance(device, XknxWeather):
            entities.append(KNXWeather(device))
    async_add_entities(entities)


class KNXWeather(WeatherEntity):
    """Representation of a KNX weather device."""

    def __init__(self, device: XknxWeather):
        """Initialize of a KNX sensor."""
        self.device = device

    @property
    def name(self):
        """Return the name of the weather device."""
        return self.device.name

    @property
    def temperature(self):
        """Return current temperature."""
        return self.device.temperature

    @property
    def temperature_unit(self):
        """Return temperature unit."""
        return TEMP_CELSIUS

    @property
    def pressure(self):
        """Return current air pressure."""
        # KNX returns pA - HA requires hPa
        return (
            self.device.air_pressure / 100
            if self.device.air_pressure is not None
            else None
        )

    @property
    def condition(self):
        """Return current weather condition."""
        return self.device.ha_current_state().value

    @property
    def humidity(self):
        """Return current humidity."""
        return self.device.humidity if self.device.humidity is not None else None

    @property
    def wind_speed(self):
        """Return current wind speed in km/h."""
        # KNX only supports wind speed in m/s
        return (
            self.device.wind_speed * 3.6 if self.device.wind_speed is not None else None
        )

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the device specific state attributes."""
        attr = {}

        if self.device.brightness_south:
            attr[ATTR_BRIGHTNESS_SOUTH] = self.device.brightness_south

        if self.device.brightness_north:
            attr[ATTR_BRIGHTNESS_NORTH] = self.device.brightness_north

        if self.device.brightness_east:
            attr[ATTR_BRIGHTNESS_EAST] = self.device.brightness_east

        if self.device.brightness_west:
            attr[ATTR_BRIGHTNESS_WEST] = self.device.brightness_west

        if self.device.rain_alarm:
            attr[ATTR_RAIN_ALARM] = self.device.rain_alarm

        if self.device.wind_alarm:
            attr[ATTR_WIND_ALARM] = self.device.wind_alarm

        if self.device.frost_alarm:
            attr[ATTR_FROST_ALARM] = self.device.frost_alarm

        return attr
