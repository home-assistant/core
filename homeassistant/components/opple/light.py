"""Support for the Opple light."""

from __future__ import annotations

import logging
from typing import Any

from pyoppleio.OppleLightDevice import OppleLightDevice
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    PLATFORM_SCHEMA as LIGHT_PLATFORM_SCHEMA,
    ColorMode,
    LightEntity,
)
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "opple light"

PLATFORM_SCHEMA = LIGHT_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Opple light platform."""
    name = config[CONF_NAME]
    host = config[CONF_HOST]
    entity = OppleLight(name, host)

    add_entities([entity])

    _LOGGER.debug("Init light %s %s", host, entity.unique_id)


class OppleLight(LightEntity):
    """Opple light device."""

    _attr_color_mode = ColorMode.COLOR_TEMP
    _attr_supported_color_modes = {ColorMode.COLOR_TEMP}
    _attr_min_color_temp_kelvin = 3000  # 333 Mireds
    _attr_max_color_temp_kelvin = 5700  # 175 Mireds

    def __init__(self, name, host):
        """Initialize an Opple light."""

        self._device = OppleLightDevice(host)

        self._name = name
        self._is_on = None
        self._brightness = None

    @property
    def available(self) -> bool:
        """Return True if light is available."""
        return self._device.is_online

    @property
    def unique_id(self):
        """Return unique ID for light."""
        return self._device.mac

    @property
    def name(self):
        """Return the display name of this light."""
        return self._name

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._is_on

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._brightness

    def turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        _LOGGER.debug("Turn on light %s %s", self._device.ip, kwargs)
        if not self.is_on:
            self._device.power_on = True

        if ATTR_BRIGHTNESS in kwargs and self.brightness != kwargs[ATTR_BRIGHTNESS]:
            self._device.brightness = kwargs[ATTR_BRIGHTNESS]

        if (
            ATTR_COLOR_TEMP_KELVIN in kwargs
            and self.color_temp_kelvin != kwargs[ATTR_COLOR_TEMP_KELVIN]
        ):
            self._device.color_temperature = kwargs[ATTR_COLOR_TEMP_KELVIN]

    def turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        self._device.power_on = False
        _LOGGER.debug("Turn off light %s", self._device.ip)

    def update(self) -> None:
        """Synchronize state with light."""
        prev_available = self.available
        self._device.update()

        if (
            prev_available == self.available
            and self._is_on == self._device.power_on
            and self._brightness == self._device.brightness
            and self._attr_color_temp_kelvin == self._device.color_temperature
        ):
            return

        if not self.available:
            _LOGGER.debug("Light %s is offline", self._device.ip)
            return

        self._is_on = self._device.power_on
        self._brightness = self._device.brightness
        self._attr_color_temp_kelvin = self._device.color_temperature

        if not self.is_on:
            _LOGGER.debug("Update light %s success: power off", self._device.ip)
        else:
            _LOGGER.debug(
                "Update light %s success: power on brightness %s color temperature %s",
                self._device.ip,
                self._brightness,
                self._attr_color_temp_kelvin,
            )
