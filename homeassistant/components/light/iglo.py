"""
Support for lights under the iGlo brand.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.iglo/
"""
import logging
import math

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_RGB_COLOR, PLATFORM_SCHEMA,
    SUPPORT_BRIGHTNESS, SUPPORT_COLOR_TEMP, SUPPORT_RGB_COLOR, Light)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
import homeassistant.helpers.config_validation as cv
import homeassistant.util.color as color_util

REQUIREMENTS = ['iglo==1.1.3']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'iGlo Light'
DEFAULT_PORT = 8080

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the iGlo lights."""
    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    port = config.get(CONF_PORT)
    add_devices([IGloLamp(name, host, port)], True)


class IGloLamp(Light):
    """Representation of an iGlo light."""

    def __init__(self, name, host, port):
        """Initialize the light."""
        from iglo import Lamp
        self._name = name
        self._lamp = Lamp(0, host, port)
        self._on = True
        self._brightness = 255
        self._rgb = (0, 0, 0)
        self._color_temp = 0

    @property
    def name(self):
        """Return the name of the light."""
        return self._name

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return int((self._brightness / 200.0) * 255)

    @property
    def color_temp(self):
        """Return the color temperature."""
        return color_util.color_temperature_kelvin_to_mired(self._color_temp)

    @property
    def min_mireds(self):
        """Return the coldest color_temp that this light supports."""
        return math.ceil(color_util.color_temperature_kelvin_to_mired(
            self._lamp.max_kelvin))

    @property
    def max_mireds(self):
        """Return the warmest color_temp that this light supports."""
        return math.ceil(color_util.color_temperature_kelvin_to_mired(
            self._lamp.min_kelvin))

    @property
    def rgb_color(self):
        """Return the RGB value."""
        return self._rgb

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP | SUPPORT_RGB_COLOR

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._on

    def turn_on(self, **kwargs):
        """Turn the light on."""
        if not self._on:
            self._lamp.switch(True)
        if ATTR_BRIGHTNESS in kwargs:
            brightness = int((kwargs[ATTR_BRIGHTNESS] / 255.0) * 200.0)
            self._lamp.brightness(brightness)
            return

        if ATTR_RGB_COLOR in kwargs:
            rgb = kwargs[ATTR_RGB_COLOR]
            self._lamp.rgb(*rgb)
            return

        if ATTR_COLOR_TEMP in kwargs:
            kelvin = int(color_util.color_temperature_mired_to_kelvin(
                kwargs[ATTR_COLOR_TEMP]))
            self._lamp.white(kelvin)
            return

    def turn_off(self, **kwargs):
        """Turn the light off."""
        self._lamp.switch(False)

    def update(self):
        """Update light status."""
        state = self._lamp.state()
        self._on = state['on']
        self._brightness = state['brightness']
        self._rgb = state['rgb']
        self._color_temp = state['white']
