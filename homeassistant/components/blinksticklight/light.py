"""Support for Blinkstick lights."""
import logging

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_HS_COLOR, SUPPORT_BRIGHTNESS, SUPPORT_COLOR, Light,
    PLATFORM_SCHEMA)
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv
import homeassistant.util.color as color_util

_LOGGER = logging.getLogger(__name__)

CONF_SERIAL = 'serial'

DEFAULT_NAME = 'Blinkstick'

SUPPORT_BLINKSTICK = SUPPORT_BRIGHTNESS | SUPPORT_COLOR

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SERIAL): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up Blinkstick device specified by serial number."""
    from blinkstick import blinkstick

    name = config.get(CONF_NAME)
    serial = config.get(CONF_SERIAL)

    stick = blinkstick.find_by_serial(serial)

    add_entities([BlinkStickLight(stick, name)], True)


class BlinkStickLight(Light):
    """Representation of a BlinkStick light."""

    def __init__(self, stick, name):
        """Initialize the light."""
        self._stick = stick
        self._name = name
        self._serial = stick.get_serial()
        self._hs_color = None
        self._brightness = None

    @property
    def should_poll(self):
        """Set up polling."""
        return True

    @property
    def name(self):
        """Return the name of the light."""
        return self._name

    @property
    def brightness(self):
        """Read back the brightness of the light."""
        return self._brightness

    @property
    def hs_color(self):
        """Read back the color of the light."""
        return self._hs_color

    @property
    def is_on(self):
        """Return True if entity is on."""
        return self._brightness > 0

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BLINKSTICK

    def update(self):
        """Read back the device state."""
        rgb_color = self._stick.get_color()
        hsv = color_util.color_RGB_to_hsv(*rgb_color)
        self._hs_color = hsv[:2]
        self._brightness = hsv[2]

    def turn_on(self, **kwargs):
        """Turn the device on."""
        if ATTR_HS_COLOR in kwargs:
            self._hs_color = kwargs[ATTR_HS_COLOR]
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]
        else:
            self._brightness = 255

        rgb_color = color_util.color_hsv_to_RGB(
            self._hs_color[0], self._hs_color[1], self._brightness / 255 * 100)
        self._stick.set_color(
            red=rgb_color[0], green=rgb_color[1], blue=rgb_color[2])

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._stick.turn_off()
