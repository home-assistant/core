"""Support for Zengge lights."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from zengge import zengge

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    ATTR_WHITE,
    PLATFORM_SCHEMA as LIGHT_PLATFORM_SCHEMA,
    ColorMode,
    LightEntity,
)
from homeassistant.const import CONF_DEVICES, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.color as color_util

_LOGGER = logging.getLogger(__name__)

DEVICE_SCHEMA = vol.Schema({vol.Optional(CONF_NAME): cv.string})

PLATFORM_SCHEMA = LIGHT_PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_DEVICES, default={}): {cv.string: DEVICE_SCHEMA}}
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Zengge platform."""
    lights = []
    for address, device_config in config[CONF_DEVICES].items():
        light = ZenggeLight(device_config[CONF_NAME], address)
        if light.is_valid:
            lights.append(light)

    add_entities(lights, True)


class ZenggeLight(LightEntity):
    """Representation of a Zengge light."""

    _attr_supported_color_modes = {ColorMode.HS, ColorMode.WHITE}

    def __init__(self, name: str, address: str) -> None:
        """Initialize the light."""

        self._attr_name = name
        self._attr_unique_id = address
        self.is_valid = True
        self._bulb = zengge(address)
        self._white = 0
        self._attr_brightness = 0
        self._attr_hs_color = (0, 0)
        self._attr_is_on = False
        if self._bulb.connect() is False:
            self.is_valid = False
            _LOGGER.error("Failed to connect to bulb %s, %s", address, name)
            return

    @property
    def white_value(self) -> int:
        """Return the white property."""
        return self._white

    @property
    def color_mode(self) -> ColorMode:
        """Return the current color mode."""
        if self._white != 0:
            return ColorMode.WHITE
        return ColorMode.HS

    def _set_rgb(self, red: int, green: int, blue: int) -> None:
        """Set the rgb state."""
        self._bulb.set_rgb(red, green, blue)

    def _set_white(self, white):
        """Set the white state."""
        return self._bulb.set_white(white)

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the specified light on."""
        self._attr_is_on = True
        self._bulb.on()

        hs_color = kwargs.get(ATTR_HS_COLOR)
        white = kwargs.get(ATTR_WHITE)
        brightness = kwargs.get(ATTR_BRIGHTNESS)

        if white is not None:
            # Change the bulb to white
            self._attr_brightness = white
            self._white = white
            self._attr_hs_color = (0, 0)

        if hs_color is not None:
            # Change the bulb to hs
            self._white = 0
            self._attr_hs_color = hs_color

        if brightness is not None:
            self._attr_brightness = brightness

        if self._white != 0:
            self._set_white(self.brightness)
        else:
            assert self.hs_color is not None
            assert self.brightness is not None
            rgb = color_util.color_hsv_to_RGB(
                self.hs_color[0], self.hs_color[1], self.brightness / 255 * 100
            )
            self._set_rgb(*rgb)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the specified light off."""
        self._attr_is_on = False
        self._bulb.off()

    def update(self) -> None:
        """Synchronise internal state with the actual light state."""
        rgb = self._bulb.get_colour()
        hsv = color_util.color_RGB_to_hsv(*rgb)
        self._attr_hs_color = hsv[:2]
        self._attr_brightness = int((hsv[2] / 100) * 255)
        self._white = self._bulb.get_white()
        if self._white:
            self._attr_brightness = self._white
        self._attr_is_on = self._bulb.get_on()
