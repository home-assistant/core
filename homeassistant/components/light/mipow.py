"""
Support for Mipow lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.mipow/
"""
import logging

import voluptuous as vol

from homeassistant.const import CONF_DEVICES, CONF_NAME
from homeassistant.components.light import (
    ATTR_RGB_COLOR, ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS,
    SUPPORT_RGB_COLOR, Light,
    FLASH_LONG, ATTR_WHITE_VALUE,
    FLASH_SHORT,
    SUPPORT_FLASH, ATTR_FLASH, PLATFORM_SCHEMA, SUPPORT_WHITE_VALUE)
import homeassistant.helpers.config_validation as cv
REQUIREMENTS = ['mipow==0.2']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'mipow'

SUPPORT_MIPOW_LED = (SUPPORT_RGB_COLOR |
                     SUPPORT_FLASH | SUPPORT_BRIGHTNESS | SUPPORT_WHITE_VALUE)

DEVICE_SCHEMA = vol.Schema({
    vol.Optional(CONF_NAME): cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_DEVICES, default={}): {cv.string: DEVICE_SCHEMA},
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Mipow platform."""
    lights = []
    for address, device_config in config[CONF_DEVICES].items():
        device = {}
        device['name'] = device_config[CONF_NAME]
        device['address'] = address
        light = MipowLight(device)
        if light.is_valid:
            lights.append(light)

    add_devices(lights)


class MipowLight(Light):
    """Representation of a Mipow light."""

    def __init__(self, device):
        """Initialize the light."""
        import mipow
        self._speed = 0
        self._name = device['name']
        self._address = device['address']
        self.is_valid = True
        self._bulb = mipow.mipow(self._address)
        self._white = 0
        self._rgb = (0, 0, 0)
        self.r = 0
        self.g = 0
        self.b = 0
        self.h = 0
        self.s = 0
        self.v = 0
        self._brightness = 0
        self._state = False
        if self._bulb.connect() is False:
            self.is_valid = False
            _LOGGER.error(
                "Failed to connect to bulb %s, %s", self._address, self._name)
        self.update()

    @property
    def unique_id(self):
        """Return the ID of this light."""
        return "{}.{}".format(self.__class__, self._address)

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def rgb_color(self):
        """Return the color property."""
        return self._rgb

    @property
    def white_value(self):
        """Return the white property."""
        return self._white

    @property
    def brightness(self):
        """Return the bright property."""
        return self._brightness

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_MIPOW_LED

    @property
    def should_poll(self):
        """Feel free to poll."""
        return True

    @property
    def assumed_state(self):
        """We can report the actual state."""
        return False

    def set_effect(self, red, green, blue, white, speed):
        """Set the rgb state."""
        return self._bulb.set_effect(red, green, blue, white, 0, speed)

    def set_rgb(self, red, green, blue):
        """Set the rgb state."""
        return self._bulb.set_rgb(red, green, blue)

    def set_white(self, white):
        """Set the white state."""
        return self._bulb.set_white(white)

    def get_bright(self):
        """Return Brightness."""
        rgb = self._bulb.get_colour()
        hsv = self.hsvconv(rgb[0], rgb[1], rgb[2])
        return (hsv[2]) * 255

    def rgbconv(self, hue, sat, val):
        """Used to convert hsv to rgb."""
        import colorsys
        rgb = colorsys.hsv_to_rgb(hue, sat, val)
        return rgb

    def hsvconv(self, re, gr, bl):
        """Used to convert rgb to hsv."""
        import colorsys
        hsv = colorsys.rgb_to_hsv(re/255, gr/255, bl/255)
        return hsv

    def turn_on(self, **kwargs):
        """Turn the specified light on."""
        rgb = kwargs.get(ATTR_RGB_COLOR)
        white = kwargs.get(ATTR_WHITE_VALUE)
        bright = kwargs.get(ATTR_BRIGHTNESS)
        flash = kwargs.get(ATTR_FLASH)
        if self._state is False:
            if rgb is None and bright is None and flash is None:
                self._white = 255
                white = 255
                self._state = True
                self._bulb.on()
        self._state = True

        if flash is not None:
            if flash == FLASH_LONG:
                self._speed = 2
            elif flash == FLASH_SHORT:
                self._speed = 1

        if bright is not None:
            rgbs = self._bulb.get_colour()
            hsvs = self.hsvconv(rgbs[0], rgbs[1], rgbs[2])
            bri = bright / 255
            rgbv = self.rgbconv(hsvs[0], hsvs[1], bri)
            respred = int(round(rgbv[0]*255))
            respgreen = int(round(rgbv[1]*255))
            respblue = int(round(rgbv[2]*255))
            self._rgb = (respred, respgreen, respblue)
            self._white = 0
        elif rgb is not None:
            self._white = 0
            self._rgb = rgb
        elif white is not None:
            self._white = white
            self._brightness = 0
            self._rgb = (0, 0, 0)
        if bright is not None:
            self.set_rgb(self._rgb[0], self._rgb[1], self._rgb[2])
        elif self._white != 0 and flash is None:
            self.set_white(self._white)
        elif flash is not None:
            self.set_effect(self._rgb[0], self._rgb[1], self._rgb[2],
                            self._white, self._speed)
        else:
            self.set_rgb(self._rgb[0], self._rgb[1], self._rgb[2])

    def turn_off(self, **kwargs):
        """Turn the specified light off."""
        self._state = False
        self._bulb.off()

    def update(self):
        """Update status."""
        self._rgb = self._bulb.get_colour()
        self._white = self._bulb.get_white()
        self._state = self._bulb.get_on()
        self._brightness = self.get_bright()
