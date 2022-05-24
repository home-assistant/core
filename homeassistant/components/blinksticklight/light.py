"""Support for Blinkstick lights."""
from __future__ import annotations

from blinkstick import blinkstick
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    PLATFORM_SCHEMA,
    ColorMode,
    LightEntity,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.color as color_util

CONF_SERIAL = "serial"

DEFAULT_NAME = "Blinkstick"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_SERIAL): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up Blinkstick device specified by serial number."""

    name = config[CONF_NAME]
    serial = config[CONF_SERIAL]

    stick = blinkstick.find_by_serial(serial)

    add_entities([BlinkStickLight(stick, name)], True)


class BlinkStickLight(LightEntity):
    """Representation of a BlinkStick light."""

    _attr_color_mode = ColorMode.HS
    _attr_supported_color_modes = {ColorMode.HS}

    def __init__(self, stick, name):
        """Initialize the light."""
        self._stick = stick
        self._attr_name = name

    def update(self):
        """Read back the device state."""
        rgb_color = self._stick.get_color()
        hsv = color_util.color_RGB_to_hsv(*rgb_color)
        self._attr_hs_color = hsv[:2]
        self._attr_brightness = hsv[2]
        self._attr_is_on = self.brightness > 0

    def turn_on(self, **kwargs):
        """Turn the device on."""
        if ATTR_HS_COLOR in kwargs:
            self._attr_hs_color = kwargs[ATTR_HS_COLOR]
        if ATTR_BRIGHTNESS in kwargs:
            self._attr_brightness = kwargs[ATTR_BRIGHTNESS]
        else:
            self._attr_brightness = 255
        self._attr_is_on = self.brightness > 0

        rgb_color = color_util.color_hsv_to_RGB(
            self.hs_color[0], self.hs_color[1], self.brightness / 255 * 100
        )
        self._stick.set_color(red=rgb_color[0], green=rgb_color[1], blue=rgb_color[2])

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._stick.turn_off()
