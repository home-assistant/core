"""Support for lights under the iGlo brand."""

from __future__ import annotations

import math
from typing import Any

from iglo import Lamp
from iglo.lamp import MODE_WHITE
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    PLATFORM_SCHEMA,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.color as color_util

DEFAULT_NAME = "iGlo Light"
DEFAULT_PORT = 8080

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the iGlo lights."""
    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    port = config.get(CONF_PORT)
    add_entities([IGloLamp(name, host, port)], True)


class IGloLamp(LightEntity):
    """Representation of an iGlo light."""

    _attr_supported_color_modes = {ColorMode.COLOR_TEMP, ColorMode.HS}
    _attr_supported_features = LightEntityFeature.EFFECT

    def __init__(self, name, host, port):
        """Initialize the light."""

        self._name = name
        self._lamp = Lamp(0, host, port)

    @property
    def name(self):
        """Return the name of the light."""
        return self._name

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return int((self._lamp.state()["brightness"] / 200.0) * 255)

    @property
    def color_mode(self) -> ColorMode:
        """Return the color mode of the light."""
        if self._lamp.state()["mode"] == MODE_WHITE:
            return ColorMode.COLOR_TEMP
        # The iglo library reports MODE_WHITE when an effect is active, this is not
        # supported by Home Assistant, just report ColorMode.HS
        return ColorMode.HS

    @property
    def color_temp(self):
        """Return the color temperature."""
        return color_util.color_temperature_kelvin_to_mired(self._lamp.state()["white"])

    @property
    def min_mireds(self) -> int:
        """Return the coldest color_temp that this light supports."""
        return math.ceil(
            color_util.color_temperature_kelvin_to_mired(self._lamp.max_kelvin)
        )

    @property
    def max_mireds(self) -> int:
        """Return the warmest color_temp that this light supports."""
        return math.ceil(
            color_util.color_temperature_kelvin_to_mired(self._lamp.min_kelvin)
        )

    @property
    def hs_color(self):
        """Return the hs value."""
        return color_util.color_RGB_to_hs(*self._lamp.state()["rgb"])

    @property
    def effect(self):
        """Return the current effect."""
        return self._lamp.state()["effect"]

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return self._lamp.effect_list()

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._lamp.state()["on"]

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        if not self.is_on:
            self._lamp.switch(True)
        if ATTR_BRIGHTNESS in kwargs:
            brightness = int((kwargs[ATTR_BRIGHTNESS] / 255.0) * 200.0)
            self._lamp.brightness(brightness)
            return

        if ATTR_HS_COLOR in kwargs:
            rgb = color_util.color_hs_to_RGB(*kwargs[ATTR_HS_COLOR])
            self._lamp.rgb(*rgb)
            return

        if ATTR_COLOR_TEMP in kwargs:
            kelvin = int(
                color_util.color_temperature_mired_to_kelvin(kwargs[ATTR_COLOR_TEMP])
            )
            self._lamp.white(kelvin)
            return

        if ATTR_EFFECT in kwargs:
            effect = kwargs[ATTR_EFFECT]
            self._lamp.effect(effect)
            return

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        self._lamp.switch(False)
