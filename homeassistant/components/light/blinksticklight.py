"""
Support for Blinkstick lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.blinksticklight/
"""
import logging

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_RGB_COLOR, SUPPORT_RGB_COLOR, Light, PLATFORM_SCHEMA)
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['blinkstick==1.1.8']

_LOGGER = logging.getLogger(__name__)

CONF_SERIAL = 'serial'

DEFAULT_NAME = 'Blinkstick'

SUPPORT_BLINKSTICK = SUPPORT_RGB_COLOR

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SERIAL): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up Blinkstick device specified by serial number."""
    from blinkstick import blinkstick

    name = config.get(CONF_NAME)
    serial = config.get(CONF_SERIAL)

    stick = blinkstick.find_by_serial(serial)

    add_devices([BlinkStickLight(stick, name)])


class BlinkStickLight(Light):
    """Representation of a BlinkStick light."""

    def __init__(self, stick, name):
        """Initialize the light."""
        self._stick = stick
        self._name = name
        self._serial = stick.get_serial()
        self._rgb_color = stick.get_color()

    @property
    def should_poll(self):
        """Set up polling."""
        return True

    @property
    def name(self):
        """Return the name of the light."""
        return self._name

    @property
    def rgb_color(self):
        """Read back the color of the light."""
        return self._rgb_color

    @property
    def is_on(self):
        """Check whether any of the LEDs colors are non-zero."""
        return sum(self._rgb_color) > 0

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BLINKSTICK

    def update(self):
        """Read back the device state."""
        self._rgb_color = self._stick.get_color()

    def turn_on(self, **kwargs):
        """Turn the device on."""
        if ATTR_RGB_COLOR in kwargs:
            self._rgb_color = kwargs[ATTR_RGB_COLOR]
        else:
            self._rgb_color = [255, 255, 255]

        self._stick.set_color(red=self._rgb_color[0],
                              green=self._rgb_color[1],
                              blue=self._rgb_color[2])

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._stick.turn_off()
