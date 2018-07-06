"""
Support for lights that use the HTTP protocol.
For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.pwm/
"""
import logging

import voluptuous as vol

import requests

from homeassistant.const import CONF_HOST, CONF_NAME, CONF_TYPE
from homeassistant.components.light import (
    Light, ATTR_BRIGHTNESS, ATTR_HS_COLOR, ATTR_TRANSITION, 
    SUPPORT_BRIGHTNESS, SUPPORT_COLOR, PLATFORM_SCHEMA)
import homeassistant.helpers.config_validation as cv
import homeassistant.util.color as color_util

REQUIREMENTS = ['requests==2.19.1']

_LOGGER = logging.getLogger(__name__)

CONF_TYPE_SIMPLE = 'simple'
CONF_TYPE_DIMMABLE = 'dimmable'
CONF_TYPE_RGB = 'color'

CONF_TYPES = [CONF_TYPE_SIMPLE, CONF_TYPE_DIMMABLE, CONF_TYPE_RGB]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_TYPE): vol.In(CONF_TYPES)
})

SUPPORT_HTTPLIGHT_BRIGHTNESS = SUPPORT_BRIGHTNESS
SUPPORT_HTTPLIGHT_RGB = SUPPORT_BRIGHTNESS | SUPPORT_COLOR


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup HTTP Light platform for required type."""

    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    lighttype = config.get(CONF_TYPE)

    if lighttype == CONF_TYPE_DIMMABLE:
        add_devices([HTTPLightDimmable(host, name)])
    elif lighttype == CONF_TYPE_RGB:
        add_devices([HTTPLightRGB(host, name)])
    else:
        add_devices([HTTPLightSimple(host, name)])


class HTTPLightSimple(Light):
    """Simple HTTP Light supports on and off."""
    def __init__(self, host, name):
        self._name = name
        self._host = host
        self._state = False

    @property
    def name(self):
        return self._name

    @property
    def is_on(self):
        return self._state
    
    def update(self):
        getState = requests.get(url = 'http://' + str(self._host) + '/state')
        if getState.text.partition('\r\n')[0] == 'on':
            self._state = True
        elif getState.text.partition('\r\n')[0] == 'off':
            self._state = False

    def turn_on(self):
        requests.post(url = 'http://' + str(self._host) + '/on')

    def turn_off(self):
        requests.post(url = 'http://' + str(self._host) + '/off')


class HTTPLightDimmable(Light):
    """Dimmable HTTP Light supports on, off and brightness."""
    def __init__(self, host, name):
        self._name = name
        self._host = host
        self._state = False
        self._brightness = 0
    
    @property
    def name(self):
        return self._name

    @property
    def is_on(self):
        return self._state

    @property
    def brightness(self):
        return self._brightness

    @property
    def supported_features(self):
        return SUPPORT_HTTPLIGHT_BRIGHTNESS
    

    def update(self):
        getBrightness = requests.get(url = 'http://' + str(self._host) + '/brightness')
        brightness = getBrightness.text.partition('\r\n')[0]
        self._brightness = int(int(brightness) * 2.55)
        if int(int(brightness) * 2.55) > 0:
            self._state = True
        else:
            self._state = False
        
    def turn_on(self, **kwargs):
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]
        else:
            self._brightness = 255
        requests.post(url = 'http://' + str(self._host) + '/set' + str(int(self._brightness / 2.55)))

    def turn_off(self):
        requests.post(url = 'http://' + str(self._host) + '/off')


class HTTPLightRGB(Light):
    """Color HTTP Light supports on, off, brightness and color."""
    def __init__(self, host, name):
        self._name = name
        self._host = host
        self._state = False
        self._brightness = 0
        self._hs_color = None
    
    @property
    def name(self):
        return self._name

    @property
    def is_on(self):
        return self._state

    @property
    def brightness(self):
        return self._brightness

    @property
    def hs_color(self):
        return self._hs_color

    @property
    def supported_features(self):
        return SUPPORT_HTTPLIGHT_RGB
    

    def update(self):
        getHex = requests.get(url = 'http://' + str(self._host) + '/color')
        getBrightness = requests.get(url = 'http://' + str(self._host) + '/brightness')
        rgb_color = tuple(int(getHex.text.partition('\r\n')[0][i:i+2], 16) for i in (0, 2 ,4))
        hsvcolor = color_util.color_RGB_to_hsv(rgb_color[0], rgb_color[1], rgb_color[2])
        self._brightness = int(int(getBrightness.text) * 2.55)
        self._hs_color = hsvcolor[:2] 
        if int(getBrightness.text) > 0:
            self._state = True
        else:
            self._state = False
        
    def turn_on(self, **kwargs):
        if ATTR_HS_COLOR in kwargs:
            self._hs_color = kwargs[ATTR_HS_COLOR]
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]
        else:
            self._brightness = 255

        rgb_color = color_util.color_hsv_to_RGB(
            self._hs_color[0], self._hs_color[1], self._brightness / 255 * 100)
        hexcolor = '%02x%02x%02x' % (int(rgb_color[0]), int(rgb_color[1]), int(rgb_color[2]))
        requests.post(url = 'http://' + str(self._host) + '/set' + str(hexcolor))

    def turn_off(self):
        requests.post(url = 'http://' + str(self._host) + '/off')
