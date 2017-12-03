"""
Support for TPLink lights.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/light.tplink/
"""
import logging
import colorsys
import time

from homeassistant.const import (CONF_HOST, CONF_NAME)
from homeassistant.components.light import (
    Light, ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_KELVIN, ATTR_RGB_COLOR,
    SUPPORT_BRIGHTNESS, SUPPORT_COLOR_TEMP, SUPPORT_RGB_COLOR)
from homeassistant.util.color import \
    color_temperature_mired_to_kelvin as mired_to_kelvin
from homeassistant.util.color import (
    color_temperature_kelvin_to_mired as kelvin_to_mired)

from typing import Tuple

REQUIREMENTS = ['pyHS100==0.3.0']

_LOGGER = logging.getLogger(__name__)

ATTR_CURRENT_CONSUMPTION = 'current_consumption'
ATTR_DAILY_CONSUMPTION = 'daily_consumption'
ATTR_MONTHLY_CONSUMPTION = 'monthly_consumption'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Initialise pyLB100 SmartBulb."""
    from pyHS100 import SmartBulb
    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    add_devices([TPLinkSmartBulb(SmartBulb(host), name)], True)


def brightness_to_percentage(byt):
    """Convert brightness from absolute 0..255 to percentage."""
    return int((byt*100.0)/255.0)


def brightness_from_percentage(percent):
    """Convert percentage to absolute value 0..255."""
    return (percent*255.0)/100.0


# Travis-CI runs too old astroid https://github.com/PyCQA/pylint/issues/1212
# pylint: disable=invalid-sequence-index
def rgb_to_hsv(rgb: Tuple[float, float, float]) -> Tuple[int, int, int]:
    """Convert RGB tuple (values 0-255) to HSV (degrees, %, %)."""
    hue, sat, value = colorsys.rgb_to_hsv(rgb[0]/255, rgb[1]/255, rgb[2]/255)
    return int(hue * 360), int(sat * 100), int(value * 100)


# Travis-CI runs too old astroid https://github.com/PyCQA/pylint/issues/1212
# pylint: disable=invalid-sequence-index
def hsv_to_rgb(hsv: Tuple[float, float, float]) -> Tuple[int, int, int]:
    """Convert HSV tuple (degrees, %, %) to RGB (values 0-255)."""
    red, green, blue = colorsys.hsv_to_rgb(hsv[0]/360, hsv[1]/100, hsv[2]/100)
    return int(red * 255), int(green * 255), int(blue * 255)


class TPLinkSmartBulb(Light):
    """Representation of a TPLink Smart Bulb."""

    def __init__(self, smartbulb: 'SmartBulb', name):
        """Initialize the bulb."""
        self.smartbulb = smartbulb
        self._name = None
        if name is not None:
            self._name = name
        self._state = None
        self._color_temp = None
        self._brightness = None
        self._rgb = None
        self._supported_features = 0
        self._emeter_params = {}

    @property
    def name(self):
        """Return the name of the Smart Bulb, if any."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._emeter_params

    def turn_on(self, **kwargs):
        """Turn the light on."""
        self.smartbulb.state = self.smartbulb.BULB_STATE_ON

        if ATTR_COLOR_TEMP in kwargs:
            self.smartbulb.color_temp = \
                mired_to_kelvin(kwargs[ATTR_COLOR_TEMP])
        if ATTR_KELVIN in kwargs:
            self.smartbulb.color_temp = kwargs[ATTR_KELVIN]
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs.get(ATTR_BRIGHTNESS, self.brightness or 255)
            self.smartbulb.brightness = brightness_to_percentage(brightness)
        if ATTR_RGB_COLOR in kwargs:
            rgb = kwargs.get(ATTR_RGB_COLOR)
            self.smartbulb.hsv = rgb_to_hsv(rgb)

    def turn_off(self):
        """Turn the light off."""
        self.smartbulb.state = self.smartbulb.BULB_STATE_OFF

    @property
    def color_temp(self):
        """Return the color temperature of this light in mireds for HA."""
        return self._color_temp

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def rgb_color(self):
        """Return the color in RGB."""
        return self._rgb

    @property
    def is_on(self):
        """Return True if device is on."""
        return self._state

    def update(self):
        """Update the TP-Link Bulb's state."""
        from pyHS100 import SmartDeviceException
        try:
            if self._supported_features == 0:
                self.get_features()
            self._state = (
                self.smartbulb.state == self.smartbulb.BULB_STATE_ON)
            if self._name is None:
                self._name = self.smartbulb.alias
            if self._supported_features & SUPPORT_BRIGHTNESS:
                self._brightness = brightness_from_percentage(
                    self.smartbulb.brightness)
            if self._supported_features & SUPPORT_COLOR_TEMP:
                if (self.smartbulb.color_temp is not None and
                        self.smartbulb.color_temp != 0):
                    self._color_temp = kelvin_to_mired(
                        self.smartbulb.color_temp)
            if self._supported_features & SUPPORT_RGB_COLOR:
                self._rgb = hsv_to_rgb(self.smartbulb.hsv)
            if self.smartbulb.has_emeter:
                self._emeter_params[ATTR_CURRENT_CONSUMPTION] \
                    = "%.1f W" % self.smartbulb.current_consumption()
                daily_statistics = self.smartbulb.get_emeter_daily()
                monthly_statistics = self.smartbulb.get_emeter_monthly()
                try:
                    self._emeter_params[ATTR_DAILY_CONSUMPTION] \
                        = "%.2f kW" % daily_statistics[int(
                            time.strftime("%d"))]
                    self._emeter_params[ATTR_MONTHLY_CONSUMPTION] \
                        = "%.2f kW" % monthly_statistics[int(
                            time.strftime("%m"))]
                except KeyError:
                    # device returned no daily/monthly history
                    pass
        except (SmartDeviceException, OSError) as ex:
            _LOGGER.warning('Could not read state for %s: %s', self._name, ex)

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._supported_features

    def get_features(self):
        """Determine all supported features in one go."""
        if self.smartbulb.is_dimmable:
            self._supported_features += SUPPORT_BRIGHTNESS
        if self.smartbulb.is_variable_color_temp:
            self._supported_features += SUPPORT_COLOR_TEMP
        if self.smartbulb.is_color:
            self._supported_features += SUPPORT_RGB_COLOR
