"""
Support for TPLink lights.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/light.tplink/
"""
import logging
from homeassistant.const import (CONF_HOST, CONF_NAME)
from homeassistant.components.light import (
    Light, ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_KELVIN, ATTR_RGB_COLOR,
    SUPPORT_BRIGHTNESS, SUPPORT_COLOR_TEMP, SUPPORT_RGB_COLOR)
from homeassistant.util.color import \
    color_temperature_mired_to_kelvin as mired_to_kelvin
from homeassistant.util.color import (
    color_RGB_to_hsv, color_hsv_to_RGB,
    color_temperature_kelvin_to_mired as kelvin_to_mired)

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pyHS100 import SmartBulb

REQUIREMENTS = ['pyHS100==0.2.4.2']

_LOGGER = logging.getLogger(__name__)

SUPPORT_TPLINK = (SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP)


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


class TPLinkSmartBulb(Light):
    """Representation of a TPLink Smart Bulb."""

    def __init__(self, smartbulb, name):
        """Initialize the bulb."""
        self.smartbulb = smartbulb  # type: SmartBulb

        # Use the name set on the device if not set
        if name is None:
            self._name = self.smartbulb.alias
        else:
            self._name = name

        self._state = None
        self._color_temp = None
        self._brightness = None
        self._rgb = None
        _LOGGER.debug("Setting up TP-Link Smart Bulb")

    @property
    def name(self):
        """Return the name of the Smart Bulb, if any."""
        return self._name

    def turn_on(self, **kwargs):
        """Turn the light on."""
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
            self._rgb = rgb
            self.smartbulb.hsv = color_RGB_to_hsv(rgb[0], rgb[1], rgb[2])

        self.smartbulb.state = self.smartbulb.BULB_STATE_ON

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
        return self._rgb

    @property
    def is_on(self):
        """True if device is on."""
        return self._state

    def update(self):
        """Update the TP-Link Bulb's state."""
        from pyHS100 import SmartPlugException
        try:
            self._state = (
                self.smartbulb.state == self.smartbulb.BULB_STATE_ON)
            self._brightness = brightness_from_percentage(
                self.smartbulb.brightness)
            if self.smartbulb.is_color:
                if (self.smartbulb.color_temp is not None and
                        self.smartbulb.color_temp != 0):
                    self._color_temp = kelvin_to_mired(
                        self.smartbulb.color_temp)
                h, s, v = self.smartbulb.hsv
                self._rgb = color_hsv_to_RGB(h, s, v)
        except (SmartPlugException, OSError) as ex:
            _LOGGER.warning('Could not read state for %s: %s', self.name, ex)

    @property
    def supported_features(self):
        """Flag supported features."""
        supported_features = SUPPORT_TPLINK
        if self.smartbulb.is_color:
            supported_features += SUPPORT_RGB_COLOR
        return supported_features
