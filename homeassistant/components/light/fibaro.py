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

    _supports_dimming = False
    _supports_color = False
    _supports_white_value = False
    _supported_features_flags = 0
    _last_brightness = 0
    _state = False
    _color = None
    _brightness = None
    _white_value = None

    def __init__(self, fibaro_device, controller):
        """Initialize the light."""
        if 'levelChange' in fibaro_device.interfaces:
            self._supported_features_flags |= SUPPORT_BRIGHTNESS
            self._supports_dimming = True
        if 'color' in fibaro_device.properties:
            self._supported_features_flags |= SUPPORT_COLOR
            self._supports_color = True
        if 'setW' in fibaro_device.actions:
            self._supports_white_value = True
            self._supported_features_flags |= SUPPORT_WHITE_VALUE
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
        return self._white_value

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._supported_features_flags

    def turn_on(self, **kwargs):
        """Turn the light on."""
        update_color = False
        if ATTR_WHITE_VALUE in kwargs:
            self._white_value = kwargs[ATTR_WHITE_VALUE]
            update_color = True
        if ATTR_HS_COLOR in kwargs and self._color:
            self._color = kwargs[ATTR_HS_COLOR]
            update_color = True
        if update_color:
            rgb = color_util.color_hs_to_RGB(*self._color)
            self.set_color(rgb, self._white_value)
        if self._supports_dimming:
            target_brightness = None
            if ATTR_BRIGHTNESS_PCT in kwargs:
                target_brightness = int(kwargs[ATTR_BRIGHTNESS_PCT]*255/100)
            elif ATTR_BRIGHTNESS in kwargs:
                target_brightness = kwargs[ATTR_BRIGHTNESS]
            if target_brightness is None:
                self._state = True
                if self._brightness < 4:
                    if self._last_brightness:
                        self._brightness = self._last_brightness
                    else:
                        self._brightness = 255
                    self.set_level(int(self._brightness*100/255))
                else:
                    self.switch_on()
            elif target_brightness < 4:
                self._brightness = 0
                self.switch_off()
                self._state = False
            else:
                self._state = True
                self._brightness = target_brightness
                self.set_level(int(target_brightness*100/255))
        else:
            self.switch_on()
            self._state = True
        self.schedule_update_ha_state(True)

    def turn_off(self, **kwargs):
        """Turn the light off."""
        if self._supports_dimming and self._brightness and \
                self._brightness >= 4:
            self._last_brightness = self._brightness
        self.switch_off()
        self._state = False
#        self.schedule_update_ha_state()

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def update(self):
        """Call to update state."""
        self._state = self.current_binary_state
        if self._supports_dimming:
            # If it is dimmable, both functions exist. In case color
            # is not supported, it will return None
            if 'brightness' in self.fibaro_device.properties:
                self._brightness = \
                    int(int(self.fibaro_device.properties.brightness)*255/100)
            else:
                self._brightness = \
                    int(int(self.fibaro_device.properties.value)*255/100)
        if self._supports_color:
            rgbw_color_str = self.fibaro_device.properties.color
            rgbw_list = [int(i) for i in rgbw_color_str.split(",")][:4]
            rgb_list = rgbw_list[:3]
            col = color_util.color_RGB_to_hs(*rgb_list) if rgb_list else None
            self._color = col
            if self._supports_white_value:
                self._white_value = rgbw_list[3]
