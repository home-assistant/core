"""Support for Zengge lights."""
import logging

import voluptuous as vol
from zengge import zengge

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    ATTR_WHITE_VALUE,
    PLATFORM_SCHEMA,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_WHITE_VALUE,
    LightEntity,
)
from homeassistant.const import CONF_DEVICES, CONF_NAME
import homeassistant.helpers.config_validation as cv
import homeassistant.util.color as color_util

_LOGGER = logging.getLogger(__name__)

SUPPORT_ZENGGE_LED = SUPPORT_BRIGHTNESS | SUPPORT_COLOR | SUPPORT_WHITE_VALUE

DEVICE_SCHEMA = vol.Schema({vol.Optional(CONF_NAME): cv.string})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_DEVICES, default={}): {cv.string: DEVICE_SCHEMA}}
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Zengge platform."""
    lights = []
    for address, device_config in config[CONF_DEVICES].items():
        device = {}
        device["name"] = device_config[CONF_NAME]
        device["address"] = address
        light = ZenggeLight(device)
        if light.is_valid:
            lights.append(light)

    add_entities(lights, True)


class ZenggeLight(LightEntity):
    """Representation of a Zengge light."""

    def __init__(self, device):
        """Initialize the light."""

        self._name = device["name"]
        self._address = device["address"]
        self.is_valid = True
        self._bulb = zengge(self._address)
        self._white = 0
        self._brightness = 0
        self._hs_color = (0, 0)
        self._state = False
        if self._bulb.connect() is False:
            self.is_valid = False
            _LOGGER.error("Failed to connect to bulb %s, %s", self._address, self._name)
            return

    @property
    def unique_id(self):
        """Return the ID of this light."""
        return self._address

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def brightness(self):
        """Return the brightness property."""
        return self._brightness

    @property
    def hs_color(self):
        """Return the color property."""
        return self._hs_color

    @property
    def white_value(self):
        """Return the white property."""
        return self._white

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_ZENGGE_LED

    @property
    def assumed_state(self):
        """We can report the actual state."""
        return False

    def set_rgb(self, red, green, blue):
        """Set the rgb state."""
        return self._bulb.set_rgb(red, green, blue)

    def set_white(self, white):
        """Set the white state."""
        return self._bulb.set_white(white)

    def turn_on(self, **kwargs):
        """Turn the specified light on."""
        self._state = True
        self._bulb.on()

        hs_color = kwargs.get(ATTR_HS_COLOR)
        white = kwargs.get(ATTR_WHITE_VALUE)
        brightness = kwargs.get(ATTR_BRIGHTNESS)

        if white is not None:
            self._white = white
            self._hs_color = (0, 0)

        if hs_color is not None:
            self._white = 0
            self._hs_color = hs_color

        if brightness is not None:
            self._white = 0
            self._brightness = brightness

        if self._white != 0:
            self.set_white(self._white)
        else:
            rgb = color_util.color_hsv_to_RGB(
                self._hs_color[0], self._hs_color[1], self._brightness / 255 * 100
            )
            self.set_rgb(*rgb)

    def turn_off(self, **kwargs):
        """Turn the specified light off."""
        self._state = False
        self._bulb.off()

    def update(self):
        """Synchronise internal state with the actual light state."""
        rgb = self._bulb.get_colour()
        hsv = color_util.color_RGB_to_hsv(*rgb)
        self._hs_color = hsv[:2]
        self._brightness = (hsv[2] / 100) * 255
        self._white = self._bulb.get_white()
        self._state = self._bulb.get_on()
