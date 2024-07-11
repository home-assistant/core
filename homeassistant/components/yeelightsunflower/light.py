"""Support for Yeelight Sunflower color bulbs (not Yeelight Blue or WiFi)."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
import yeelightsunflower

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    PLATFORM_SCHEMA as LIGHT_PLATFORM_SCHEMA,
    ColorMode,
    LightEntity,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.color as color_util

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = LIGHT_PLATFORM_SCHEMA.extend({vol.Required(CONF_HOST): cv.string})


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Yeelight Sunflower Light platform."""
    host = config.get(CONF_HOST)
    hub = yeelightsunflower.Hub(host)

    if not hub.available:
        _LOGGER.error("Could not connect to Yeelight Sunflower hub")
        return

    add_entities(SunflowerBulb(light) for light in hub.get_lights())


class SunflowerBulb(LightEntity):
    """Representation of a Yeelight Sunflower Light."""

    _attr_color_mode = ColorMode.HS
    _attr_supported_color_modes = {ColorMode.HS}

    def __init__(self, light: yeelightsunflower.Bulb) -> None:
        """Initialize a Yeelight Sunflower bulb."""
        self._light = light
        self._attr_available = light.available
        self._brightness = light.brightness
        self._attr_is_on = light.is_on
        self._rgb_color = light.rgb_color
        self._attr_unique_id = light.zid
        self._attr_name = f"sunflower_{self._light.zid}"

    @property
    def brightness(self) -> int:
        """Return the brightness is 0-255; Yeelight's brightness is 0-100."""
        return int(self._brightness / 100 * 255)

    @property
    def hs_color(self) -> tuple[float, float]:
        """Return the color property."""
        return color_util.color_RGB_to_hs(*self._rgb_color)

    def turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on, optionally set colour/brightness."""
        # when no arguments, just turn light on (full brightness)
        if not kwargs:
            self._light.turn_on()
        elif ATTR_HS_COLOR in kwargs and ATTR_BRIGHTNESS in kwargs:
            rgb = color_util.color_hs_to_RGB(*kwargs[ATTR_HS_COLOR])
            bright = int(kwargs[ATTR_BRIGHTNESS] / 255 * 100)
            self._light.set_all(rgb[0], rgb[1], rgb[2], bright)
        elif ATTR_HS_COLOR in kwargs:
            rgb = color_util.color_hs_to_RGB(*kwargs[ATTR_HS_COLOR])
            self._light.set_rgb_color(rgb[0], rgb[1], rgb[2])
        elif ATTR_BRIGHTNESS in kwargs:
            bright = int(kwargs[ATTR_BRIGHTNESS] / 255 * 100)
            self._light.set_brightness(bright)

    def turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        self._light.turn_off()

    def update(self) -> None:
        """Fetch new state data for this light and update local values."""
        self._light.update()
        self._attr_available = self._light.available
        self._brightness = self._light.brightness
        self._attr_is_on = self._light.is_on
        self._rgb_color = self._light.rgb_color
