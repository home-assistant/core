"""
Support for lights that use the HTTP protocol.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.pwm/
"""
import logging

import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_NAME, CONF_TYPE
from homeassistant.components.light import (
    Light, ATTR_BRIGHTNESS,
    ATTR_HS_COLOR, SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR, PLATFORM_SCHEMA)
import homeassistant.helpers.config_validation as cv
import homeassistant.util.color as color_util


REQUIREMENTS = ['requests==2.19.1']

_LOGGER = logging.getLogger(__name__)

CONF_TYPE_SIMPLE = 'simple'
CONF_TYPE_DIMMABLE = 'dimmable'
CONF_TYPE_COLOR = 'color'

CONF_TYPES = [CONF_TYPE_SIMPLE, CONF_TYPE_DIMMABLE, CONF_TYPE_COLOR]

SUPPORT_HTTPLIGHT_BRIGHTNESS = SUPPORT_BRIGHTNESS
SUPPORT_HTTPLIGHT_COLOR = SUPPORT_BRIGHTNESS | SUPPORT_COLOR

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_TYPE): vol.In(CONF_TYPES)
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup HTTP Light platform for required type."""
    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    light_type = config.get(CONF_TYPE)
    add_devices([HTTPLight(host, name, light_type)])


class HTTPLight(Light):
    """Simple HTTP Light supports on and off."""

    def __init__(self, host, name, light_type):
        """Initialize the light."""
        self._name = name
        self._host = host
        self._type = light_type
        self._brightness = 0
        self._hs_color = [0, 0]
        self._state = False

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._brightness

    @property
    def hs_color(self):
        """Return the color of the light."""
        return self._hs_color

    @property
    def supported_features(self):
        """Flag supported features."""
        if self._type == CONF_TYPE_DIMMABLE:
            return SUPPORT_HTTPLIGHT_BRIGHTNESS
        elif self._type == CONF_TYPE_COLOR:
            return SUPPORT_HTTPLIGHT_COLOR
        elif self._type == CONF_TYPE_SIMPLE:
            return 0

    @property
    def is_on(self):
        """Return the state of the device."""
        return self._state

    def update(self):
        """Get the state of the light."""
        import requests
        if self._type == CONF_TYPE_COLOR:
            get_hex = requests.get(url='http://' + str(self._host) + '/color')
            get_brightness = requests.get(
                url='http://' + str(self._host) + '/brightness')
            rgb_color = tuple(int(
                get_hex.text.partition(
                    '\r\n')[0][i:i+2], 16) for i in (0, 2, 4))
            hsvcolor = color_util.color_RGB_to_hsv(
                rgb_color[0], rgb_color[1], rgb_color[2])
            self._brightness = int(int(get_brightness.text) * 2.55)
            self._hs_color = hsvcolor[:2]
            self._state = bool(int(get_brightness.text) > 0)
        elif self._type == CONF_TYPE_DIMMABLE:
            get_brightness = requests.get(
                url='http://' + str(self._host) + '/brightness')
            brightness = get_brightness.text.partition('\r\n')[0]
            self._brightness = int(int(brightness) * 2.55)
            self._state = bool(int(int(brightness) * 2.55) > 0)
        else:
            get_state = requests.get(
                url='http://' + str(self._host) + '/state')
            self._state = bool(get_state.text.partition('\r\n')[0] == 'on')

    def turn_on(self, **kwargs):
        """Turn on the device."""
        import requests
        if self._type == CONF_TYPE_COLOR:
            if ATTR_HS_COLOR in kwargs:
                self._hs_color = kwargs[ATTR_HS_COLOR]
            if ATTR_BRIGHTNESS in kwargs:
                self._brightness = kwargs[ATTR_BRIGHTNESS]
            else:
                self._brightness = 255
            rgb_color = color_util.color_hsv_to_RGB(
                self._hs_color[0], self._hs_color[1],
                self._brightness / 255 * 100)
            hex_color = '%02x%02x%02x' % (
                int(rgb_color[0]), int(rgb_color[1]), int(rgb_color[2]))
            requests.post(
                url='http://' + str(self._host) + '/set' + str(hex_color))
        elif self._type == CONF_TYPE_DIMMABLE:
            if ATTR_BRIGHTNESS in kwargs:
                self._brightness = kwargs[ATTR_BRIGHTNESS]
            else:
                self._brightness = 255
            requests.post(
                url='http://' + str(self._host) + '/set' + str(int(
                    self._brightness / 2.55)))
        else:
            requests.post(url='http://' + str(self._host) + '/on')

    def turn_off(self, **kwargs):
        """Turn off the device."""
        import requests
        requests.post(url='http://' + str(self._host) + '/off')
