"""Support for Zengge lights."""
from __future__ import annotations

import logging

import voluptuous as vol
from zengge import zengge

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    ATTR_WHITE,
    PLATFORM_SCHEMA,
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

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
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
        device = {}
        device["name"] = device_config[CONF_NAME]
        device["address"] = address
        light = ZenggeLight(device)
        if light.is_valid:
            lights.append(light)

    add_entities(lights, True)


class ZenggeLight(LightEntity):
    """Representation of a Zengge light."""

    def __init__(self, device):
        """Initialize the light."""

        self._name = device["name"]
        self._address = device["address"]
        self.is_valid = True
        self._bulb = zengge(self._address)
        self._white = 0
        self._brightness = 0
        self._hs_color = (0, 0)
        self._state = False
        if self._bulb.connect() is False:
            self.is_valid = False
            _LOGGER.error("Failed to connect to bulb %s, %s", self._address, self._name)
            return

    @property
    def unique_id(self):
        """Return the ID of this light."""
        return self._address

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def brightness(self):
        """Return the brightness property."""
        return self._brightness

    @property
    def hs_color(self):
        """Return the color property."""
        return self._hs_color

    @property
    def white_value(self):
        """Return the white property."""
        return self._white

    @property
    def color_mode(self) -> ColorMode:
        """Return the current color mode."""
        if self._white != 0:
            return ColorMode.WHITE
        return ColorMode.HS

    @property
    def supported_color_modes(self) -> set[ColorMode | str]:
        """Flag supported color modes."""
        return {ColorMode.HS, ColorMode.WHITE}

    @property
    def assumed_state(self):
        """We can report the actual state."""
        return False

    def _set_rgb(self, red, green, blue):
        """Set the rgb state."""
        return self._bulb.set_rgb(red, green, blue)

    def _set_white(self, white):
        """Set the white state."""
        return self._bulb.set_white(white)

    def turn_on(self, **kwargs):
        """Turn the specified light on."""
        self._state = True
        self._bulb.on()

        hs_color = kwargs.get(ATTR_HS_COLOR)
        white = kwargs.get(ATTR_WHITE)
        brightness = kwargs.get(ATTR_BRIGHTNESS)

        if white is not None:
            # Change the bulb to white
            self._brightness = self._white = white
            self._hs_color = (0, 0)

        if hs_color is not None:
            # Change the bulb to hs
            self._white = 0
            self._hs_color = hs_color

        if brightness is not None:
            self._brightness = brightness

        if self._white != 0:
            self._set_white(self._brightness)
        else:
            rgb = color_util.color_hsv_to_RGB(
                self._hs_color[0], self._hs_color[1], self._brightness / 255 * 100
            )
            self._set_rgb(*rgb)

    def turn_off(self, **kwargs):
        """Turn the specified light off."""
        self._state = False
        self._bulb.off()

    def update(self):
        """Synchronise internal state with the actual light state."""
        rgb = self._bulb.get_colour()
        hsv = color_util.color_RGB_to_hsv(*rgb)
        self._hs_color = hsv[:2]
        self._brightness = (hsv[2] / 100) * 255
        self._white = self._bulb.get_white()
        if self._white:
            self._brightness = self._white
        self._state = self._bulb.get_on()
