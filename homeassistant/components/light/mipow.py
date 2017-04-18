"""
Support for Mipow Bluetooth smartbulbs.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.mipow/
"""
import logging

import voluptuous as vol

from homeassistant.const import CONF_DEVICES, CONF_NAME
from homeassistant.components.light import (
    ATTR_RGB_COLOR, ATTR_WHITE_VALUE, SUPPORT_RGB_COLOR, SUPPORT_WHITE_VALUE,
    Light, PLATFORM_SCHEMA)
from homeassistant.util.color import color_rgb_to_rgbw, color_rgbw_to_rgb
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['https://github.com/mjg59/python-mipow/releases/download/0.3/'
                'mipow-0.3.tar.gz#mipow==0.3']

_LOGGER = logging.getLogger(__name__)

SUPPORT_MIPOW_LED = (SUPPORT_RGB_COLOR | SUPPORT_WHITE_VALUE)

DEVICE_SCHEMA = vol.Schema({
    vol.Optional(CONF_NAME): cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_DEVICES, default={}): {cv.string: DEVICE_SCHEMA},
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up a Mipow bulb."""
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
        # pylint: disable=import-error
        import mipow

        self._name = device['name']
        self._address = device['address']
        self._white = 0
        self._rgb = (0, 0, 0)
        self._state = False
        self._bulb = mipow.mipow(self._address)
        self._bulb.connect()
        self.update()
        self.is_valid = True

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
        """Return the colour property."""
        return color_rgbw_to_rgb(self._rgb[0], self._rgb[1], self._rgb[2],
                                 self._white)

    @property
    def white_value(self):
        """Return the white property."""
        return self._white

    @property
    def supported_features(self):
        """Flag supported features."""
        if self._bulb.mono:
            return SUPPORT_WHITE_VALUE
        else:
            return SUPPORT_MIPOW_LED

    @property
    def assumed_state(self):
        """We can read the actual state."""
        return False

    def set_rgb(self, red, green, blue):
        """Set the rgb state."""
        rgbw = color_rgb_to_rgbw(red, green, blue)
        self._bulb.set_rgbw(rgbw[0], rgbw[1], rgbw[2], rgbw[3])
        self.update()

    def set_white(self, white):
        """Set the white state."""
        self._bulb.set_white(white)
        self.update()

    def turn_on(self, **kwargs):
        """Turn the specified bulb on."""
        rgb = kwargs.get(ATTR_RGB_COLOR)
        white = kwargs.get(ATTR_WHITE_VALUE)

        if white is not None:
            self.set_white(white)
        elif rgb is not None:
            self.set_rgb(rgb[0], rgb[1], rgb[2])
        else:
            self._bulb.set_rgbw(self._rgb[0], self._rgb[1], self._rgb[2],
                                self._white)

    def turn_off(self, **kwargs):
        """Turn the specified or all lights off."""
        self._state = False
        self.set_rgb(0, 0, 0)

    def update(self):
        """Synchronise internal state with that of the bulb."""
        (red, green, blue, white) = self._bulb.get_rgbw()
        if red != 0 or green != 0 or blue != 0 or white != 0:
            self._state = True
            self._white = white
            self._rgb = (red, green, blue)
