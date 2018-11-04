"""
Support for Fibaro lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.fibaro/
"""

# pylint: disable=R1715

import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_BRIGHTNESS_PCT, ATTR_HS_COLOR, ENTITY_ID_FORMAT,
    SUPPORT_BRIGHTNESS, SUPPORT_COLOR, SUPPORT_WHITE_VALUE, ATTR_WHITE_VALUE,
    Light)
import homeassistant.util.color as color_util
from homeassistant.components.fibaro import (
    FIBARO_CONTROLLER, FIBARO_DEVICES, FibaroDevice)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['fibaro']


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Perform the setup for Fibaro controller devices."""
    add_entities(
        [FibaroLight(device, hass.data[FIBARO_CONTROLLER])
         for device in hass.data[FIBARO_DEVICES]['light']], True)


class FibaroLight(FibaroDevice, Light):
    """Representation of a Fibaro Light, including dimmable."""

    _supported_flags = 0
    _last_brightness = 0
    _color = None
    _brightness = None
    _white = 0

    def __init__(self, fibaro_device, controller):
        """Initialize the light."""
        if 'levelChange' in fibaro_device.interfaces:
            self._supported_flags |= SUPPORT_BRIGHTNESS
        if 'color' in fibaro_device.properties:
            self._supported_flags |= SUPPORT_COLOR
        if 'setW' in fibaro_device.actions:
            self._supported_flags |= SUPPORT_WHITE_VALUE
        FibaroDevice.__init__(self, fibaro_device, controller)
        self.entity_id = ENTITY_ID_FORMAT.format(self.ha_id)

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._brightness

    @property
    def hs_color(self):
        """Return the color of the light."""
        return self._color

    @property
    def white_value(self):
        """Return the white value of this light between 0..255."""
        return self._white

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._supported_flags

    def turn_on(self, **kwargs):
        """Turn the light on."""
        if self._supported_flags & SUPPORT_COLOR:
            # Update based on parameters
            self._white = kwargs.get(ATTR_WHITE_VALUE, self._white)
            self._color = kwargs.get(ATTR_HS_COLOR, self._color)
            if (ATTR_WHITE_VALUE in kwargs) or (ATTR_HS_COLOR in kwargs):
                rgb = color_util.color_hs_to_RGB(*self._color)
                self.set_color(rgb, self._white)

        if self._supported_flags & SUPPORT_BRIGHTNESS:
            target_brightness = None
            if ATTR_BRIGHTNESS_PCT in kwargs:
                target_brightness = int(kwargs[ATTR_BRIGHTNESS_PCT]*255/100)
            elif ATTR_BRIGHTNESS in kwargs:
                target_brightness = kwargs[ATTR_BRIGHTNESS]

            # No brightness specified, so we either restore it to
            # last brightness or switch it on at maximum level
            if target_brightness is None:
                if self._brightness < 4:
                    if self._last_brightness:
                        self._brightness = self._last_brightness
                    else:
                        self._brightness = 255
                self.set_level(int(self._brightness*100/255))
                return
            # We're supposed to turn it on to a very very low level,
            # so instead, we switch it off
            if target_brightness < 4:
                self._brightness = 0
                self.action("turnOff")
                return
            # We set it to the target brightness and turn it on
            self._brightness = target_brightness
            self.set_level(int(target_brightness*100/255))
            return
        # The simplest case is left for last. No dimming, just switch on
        self.action("turnOn")

    def turn_off(self, **kwargs):
        """Turn the light off."""
        # Let's save the last brightness level before we switch it off
        if (self._supported_flags & SUPPORT_BRIGHTNESS) and \
                self._brightness and self._brightness >= 4:
            self._last_brightness = self._brightness

        self.action("turnOff")

    @property
    def is_on(self):
        """Return true if device is on."""
        return self.current_binary_state

    def update(self):
        """Call to update state."""
        # Brightness handling
        if self._supported_flags & SUPPORT_BRIGHTNESS:
            # Fibaro can represent brightness value in two different ways
            if 'brightness' in self.fibaro_device.properties:
                self._brightness = int(int(
                    self.fibaro_device.properties.brightness)*255/100)
            else:
                self._brightness = \
                    int(int(self.fibaro_device.properties.value)*255/100)
        # Color handling
        if self._supported_flags & SUPPORT_COLOR:
            # Fibaro communicates the color as an 'R, G, B, W' string
            rgbw_color_str = self.fibaro_device.properties.color
            rgbw_list = [int(i) for i in rgbw_color_str.split(",")][:4]
            self._color = color_util.color_RGB_to_hs(*rgbw_list[:3]) \
                if rgbw_list else None
            if self._supported_flags & SUPPORT_WHITE_VALUE:
                self._white = rgbw_list[3]
