"""
Support for HTTP_RGB lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.http_rgb/
"""
import logging

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, ATTR_RGB_COLOR, SUPPORT_RGB_COLOR,
    Light, PLATFORM_SCHEMA)
from homeassistant.const import (CONF_HOST, CONF_NAME)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['http_rgb==0.1.0']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'http_rgb'

SUPPORT_HTTP_RGB = (SUPPORT_BRIGHTNESS | SUPPORT_RGB_COLOR)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the HTTP_RGB Light platform."""
    import http_rgb

    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)

    light = http_rgb.http_rgb(host)

    device = HttpRgbLight(light, name)
    device.setup()
    add_devices([device], True)


class HttpRgbLight(Light):
    """Representation of a HTTP_RGB! Light."""

    def __init__(self, light, name):
        """Initialize a HTTP_RGB Light."""
        self._light = light
        self._name = name
        self._is_on = False
        self._brightness = 255
        self._rgb_color = [255, 255, 255]

    @property
    def name(self):
        """Return the display name of this light."""
        return self._name

    @property
    def brightness(self):
        """Read back the brightness of the light."""
        return self._brightness

    @property
    def rgb_color(self):
        """Read back the color of the light."""
        return self._rgb_color

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_HTTP_RGB

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._is_on

    def turn_on(self, **kwargs):
        """Instruct the light to turn on and set correct brightness & color."""
        if ATTR_RGB_COLOR in kwargs:
            self._rgb_color = kwargs[ATTR_RGB_COLOR]
            self._light.rgb_color(self._rgb_color)
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]
            self._light.brightness(self._brightness)

        self._is_on = True
        self._light.is_on(self._is_on)

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        self._is_on = False
        self._light.is_on(self._is_on)

    def update(self):
        """Get the remote's active color."""
        self._is_on = self._light.is_on()
        self._rgb_color = self._light.rgb_color()
        self._brightness = self._light.brightness()

    def setup(self):
        """Get the hostname of the remote."""
        self._name = self._light.name()
