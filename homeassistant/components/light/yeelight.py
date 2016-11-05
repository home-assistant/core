"""
Support for Xiaomi Yeelight Wifi color bulb.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.yeelight/
"""
import logging
import socket

import voluptuous as vol

from homeassistant.const import CONF_DEVICES, CONF_NAME
from homeassistant.components.light import (ATTR_BRIGHTNESS, ATTR_RGB_COLOR,
                                            SUPPORT_BRIGHTNESS,
                                            SUPPORT_RGB_COLOR, Light,
                                            PLATFORM_SCHEMA)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pyyeelight==1.0-beta']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'yeelight'

SUPPORT_YEELIGHT = (SUPPORT_BRIGHTNESS | SUPPORT_RGB_COLOR)

DEVICE_SCHEMA = vol.Schema({vol.Optional(CONF_NAME): cv.string, })

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_DEVICES, default={}): {cv.string: DEVICE_SCHEMA}, })


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Yeelight bulbs."""
    lights = []
    for ipaddr, device_config in config[CONF_DEVICES].items():
        device = {'name': device_config[CONF_NAME], 'ipaddr': ipaddr}
        lights.append(YeelightLight(device))

    add_devices(lights)


class YeelightLight(Light):
    """Representation of a Yeelight light."""

    def __init__(self, device):
        """Initialize the light."""
        import pyyeelight

        self._name = device['name']
        self._ipaddr = device['ipaddr']
        self.is_valid = True
        self._bulb = None
        self._state = None
        self._bright = None
        self._rgb = None
        try:
            self._bulb = pyyeelight.YeelightBulb(self._ipaddr)
        except socket.error:
            self.is_valid = False
            _LOGGER.error("Failed to connect to bulb %s, %s", self._ipaddr,
                          self._name)

    @property
    def unique_id(self):
        """Return the ID of this light."""
        return "{}.{}".format(self.__class__, self._ipaddr)

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state == self._bulb.POWER_ON

    @property
    def brightness(self):
        """Return the brightness of this light between 1..255."""
        return self._bright

    @property
    def rgb_color(self):
        """Return the color property."""
        return self._rgb

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_YEELIGHT

    def turn_on(self, **kwargs):
        """Turn the specified or all lights on."""
        if not self.is_on:
            self._bulb.turn_on()

        if ATTR_RGB_COLOR in kwargs:
            rgb = kwargs[ATTR_RGB_COLOR]
            self._bulb.set_rgb_color(rgb[0], rgb[1], rgb[2])
            self._rgb = [rgb[0], rgb[1], rgb[2]]

        if ATTR_BRIGHTNESS in kwargs:
            bright = int(kwargs[ATTR_BRIGHTNESS] * 100 / 255)
            self._bulb.set_brightness(bright)
            self._bright = kwargs[ATTR_BRIGHTNESS]

    def turn_off(self, **kwargs):
        """Turn the specified or all lights off."""
        self._bulb.turn_off()

    def update(self):
        """Synchronize state with bulb."""
        self._bulb.refresh_property()

        # Update power state
        self._state = self._bulb.get_property(self._bulb.PROPERTY_NAME_POWER)

        # Update Brightness value
        bright_percent = self._bulb.get_property(
            self._bulb.PROPERTY_NAME_BRIGHTNESS)
        bright = int(bright_percent) * 255 / 100
        # Handle 0
        if int(bright) == 0:
            self._bright = 1
        else:
            self._bright = int(bright)

        # Update RGB Value
        raw_rgb = int(
            self._bulb.get_property(self._bulb.PROPERTY_NAME_RGB_COLOR))
        red = int(raw_rgb / 65536)
        green = int((raw_rgb - (red * 65536)) / 256)
        blue = raw_rgb - (red * 65536) - (green * 256)
        self._rgb = [red, green, blue]
