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
CONF_TYPE_RGB = 'color'

CONF_TYPES = [CONF_TYPE_SIMPLE, CONF_TYPE_DIMMABLE, CONF_TYPE_RGB]

SUPPORT_HTTPLIGHT_BRIGHTNESS = SUPPORT_BRIGHTNESS
SUPPORT_HTTPLIGHT_RGB = SUPPORT_BRIGHTNESS | SUPPORT_COLOR

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

    if light_type == CONF_TYPE_DIMMABLE:
        add_devices([HTTPLightDimmable(host, name)])
    elif light_type == CONF_TYPE_RGB:
        add_devices([HTTPLightRGB(host, name)])
    else:
        add_devices([HTTPLightSimple(host, name)])


class HTTPLightSimple(Light):
    """Simple HTTP Light supports on and off."""

    def __init__(self, host, name):
        """Initialize the light."""
        self._name = name
        self._host = host
        self._state = False

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def is_on(self):
        """Return the state of the device."""
        return self._state

    def update(self):
        """Get the state of the light."""
        import requests
        get_state = requests.get(url='http://' + str(self._host) + '/state')
        self._state = bool(get_state.text.partition('\r\n')[0] == 'on')

    def turn_on(self, **kwargs):
        """Turn on the device."""
        import requests
        requests.post(url='http://' + str(self._host) + '/on')

    def turn_off(self, **kwargs):
        """Turn off the device."""
        import requests
        requests.post(url='http://' + str(self._host) + '/off')


class HTTPLightDimmable(Light):
    """Dimmable HTTP Light supports on, off and brightness."""

    def __init__(self, host, name):
        """Initialize the light."""
        self._name = name
        self._host = host
        self._state = False
        self._brightness = 0

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def is_on(self):
        """Return the state of the device."""
        return self._state

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._brightness

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_HTTPLIGHT_BRIGHTNESS

    def update(self):
        """Get the state and brightness of the light."""
        import requests
        get_brightness = requests.get(
            url='http://' + str(self._host) + '/brightness')
        brightness = get_brightness.text.partition('\r\n')[0]
        self._brightness = int(int(brightness) * 2.55)
        self._state = bool(int(int(brightness) * 2.55) > 0)

    def turn_on(self, **kwargs):
        """Turn on the device."""
        import requests
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]
        else:
            self._brightness = 255
        requests.post(
            url='http://' + str(self._host) + '/set' + str(int(
                self._brightness / 2.55)))

    def turn_off(self, **kwargs):
        """Turn off the device."""
        import requests
        requests.post(url='http://' + str(self._host) + '/off')


class HTTPLightRGB(Light):
    """Color HTTP Light supports on, off, brightness and color."""

    def __init__(self, host, name):
        """Initialize the light."""
        self._name = name
        self._host = host
        self._state = False
        self._brightness = 0
        self._hs_color = None

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def is_on(self):
        """Return the state of the device."""
        return self._state

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
        return SUPPORT_HTTPLIGHT_RGB

    def update(self):
        """Get the state, brightness and color of the light."""
        import requests
        get_hex = requests.get(url='http://' + str(self._host) + '/color')
        get_brightness = requests.get(
            url='http://' + str(self._host) + '/brightness')
        rgb_color = tuple(int(
            get_hex.text.partition('\r\n')[0][i:i+2], 16) for i in (0, 2, 4))
        hsvcolor = color_util.color_RGB_to_hsv(
            rgb_color[0], rgb_color[1], rgb_color[2])
        self._brightness = int(int(get_brightness.text) * 2.55)
        self._hs_color = hsvcolor[:2]
        self._state = bool(int(get_brightness.text) > 0)

    def turn_on(self, **kwargs):
        """Turn on the device."""
        import requests
        if ATTR_HS_COLOR in kwargs:
            self._hs_color = kwargs[ATTR_HS_COLOR]
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]
        else:
            self._brightness = 255

        rgb_color = color_util.color_hsv_to_RGB(
            self._hs_color[0], self._hs_color[1], self._brightness / 255 * 100)
        hex_color = '%02x%02x%02x' % (
            int(rgb_color[0]), int(rgb_color[1]), int(rgb_color[2]))
        requests.post(
            url='http://' + str(self._host) + '/set' + str(hex_color))

    def turn_off(self, **kwargs):
        """Turn off the device."""
        import requests
        requests.post(url='http://' + str(self._host) + '/off')
