"""Support for Blinkt! lights on Raspberry Pi."""
import importlib

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    PLATFORM_SCHEMA,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    LightEntity,
)
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv
import homeassistant.util.color as color_util

SUPPORT_BLINKT = SUPPORT_BRIGHTNESS | SUPPORT_COLOR

DEFAULT_NAME = "blinkt"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string}
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Blinkt Light platform."""
    blinkt = importlib.import_module("blinkt")

    # ensure that the lights are off when exiting
    blinkt.set_clear_on_exit()

    name = config[CONF_NAME]

    add_entities(
        [BlinktLight(blinkt, name, index) for index in range(blinkt.NUM_PIXELS)]
    )


class BlinktLight(LightEntity):
    """Representation of a Blinkt! Light."""

    _attr_supported_features = SUPPORT_BLINKT
    _attr_should_poll = False
    _attr_assumed_state = True

    def __init__(self, blinkt, name, index):
        """Initialize a Blinkt Light.

        Default brightness and white color.
        """
        self._blinkt = blinkt
        self._attr_name = f"{name}_{index}"
        self._index = index
        self._attr_is_on = False
        self._attr_brightness = 255
        self._attr_hs_color = [0, 0]

    def turn_on(self, **kwargs):
        """Instruct the light to turn on and set correct brightness & color."""
        if ATTR_HS_COLOR in kwargs:
            self._attr_hs_color = kwargs[ATTR_HS_COLOR]
        if ATTR_BRIGHTNESS in kwargs:
            self._attr_brightness = kwargs[ATTR_BRIGHTNESS]

        percent_bright = self.brightness / 255
        rgb_color = color_util.color_hs_to_RGB(*self.hs_color)
        self._blinkt.set_pixel(
            self._index, rgb_color[0], rgb_color[1], rgb_color[2], percent_bright
        )

        self._blinkt.show()

        self._attr_is_on = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        self._blinkt.set_pixel(self._index, 0, 0, 0, 0)
        self._blinkt.show()
        self._attr_is_on = False
        self.schedule_update_ha_state()
