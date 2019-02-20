"""
Support for Homematic lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.homematic/
"""
import logging

from homeassistant.components.homematic import ATTR_DISCOVER_DEVICES, HMDevice
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, ATTR_HS_COLOR, SUPPORT_COLOR,
    ATTR_EFFECT, SUPPORT_EFFECT, Light)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['homematic']

SUPPORT_HOMEMATIC = SUPPORT_BRIGHTNESS


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Homematic light platform."""
    if discovery_info is None:
        return

    devices = []
    for conf in discovery_info[ATTR_DISCOVER_DEVICES]:
        new_device = HMLight(conf)
        devices.append(new_device)

    add_entities(devices)


class HMLight(HMDevice, Light):
    """Representation of a Homematic light."""

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        # Is dimmer?
        if self._state == 'LEVEL':
            return int(self._hm_get_state() * 255)
        return None

    @property
    def is_on(self):
        """Return true if light is on."""
        try:
            return self._hm_get_state() > 0
        except TypeError:
            return False

    @property
    def supported_features(self):
        """Flag supported features."""
        if 'COLOR' in self._hmdevice.WRITENODE:
            return SUPPORT_BRIGHTNESS | SUPPORT_COLOR | SUPPORT_EFFECT
        return SUPPORT_BRIGHTNESS

    @property
    def hs_color(self):
        """Return the hue and saturation color value [float, float]."""
        if not self.supported_features & SUPPORT_COLOR:
            return None
        hue, sat = self._hmdevice.get_hs_color()
        return hue*360.0, sat*100.0

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        if not self.supported_features & SUPPORT_EFFECT:
            return None
        return self._hmdevice.get_effect_list()

    @property
    def effect(self):
        """Return the current color change program of the light."""
        if not self.supported_features & SUPPORT_EFFECT:
            return None
        return self._hmdevice.get_effect()

    def turn_on(self, **kwargs):
        """Turn the light on and/or change color or color effect settings."""
        if ATTR_BRIGHTNESS in kwargs and self._state == "LEVEL":
            percent_bright = float(kwargs[ATTR_BRIGHTNESS]) / 255
            self._hmdevice.set_level(percent_bright, self._channel)
        elif ATTR_HS_COLOR not in kwargs and ATTR_EFFECT not in kwargs:
            self._hmdevice.on(self._channel)

        if ATTR_HS_COLOR in kwargs:
            self._hmdevice.set_hs_color(
                hue=kwargs[ATTR_HS_COLOR][0]/360.0,
                saturation=kwargs[ATTR_HS_COLOR][1]/100.0)
        if ATTR_EFFECT in kwargs:
            self._hmdevice.set_effect(kwargs[ATTR_EFFECT])

    def turn_off(self, **kwargs):
        """Turn the light off."""
        self._hmdevice.off(self._channel)

    def _init_data_struct(self):
        """Generate a data dict (self._data) from the Homematic metadata."""
        # Use LEVEL
        self._state = "LEVEL"
        self._data[self._state] = None

        if self.supported_features & SUPPORT_COLOR:
            self._data.update({"COLOR": None, "PROGRAM": None})
