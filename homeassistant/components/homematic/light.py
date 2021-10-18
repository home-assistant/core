"""Support for Homematic lights."""
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    SUPPORT_EFFECT,
    SUPPORT_TRANSITION,
    LightEntity,
)

from .const import ATTR_DISCOVER_DEVICES
from .entity import HMDevice

SUPPORT_HOMEMATIC = SUPPORT_BRIGHTNESS


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Homematic light platform."""
    if discovery_info is None:
        return

    devices = []
    for conf in discovery_info[ATTR_DISCOVER_DEVICES]:
        new_device = HMLight(conf)
        devices.append(new_device)

    add_entities(devices, True)


class HMLight(HMDevice, LightEntity):
    """Representation of a Homematic light."""

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        # Is dimmer?
        if self._state == "LEVEL":
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
        features = SUPPORT_BRIGHTNESS | SUPPORT_TRANSITION

        if "COLOR" in self._hmdevice.WRITENODE:
            features |= SUPPORT_COLOR
        if "PROGRAM" in self._hmdevice.WRITENODE:
            features |= SUPPORT_EFFECT
        if hasattr(self._hmdevice, "get_color_temp"):
            features |= SUPPORT_COLOR_TEMP
        return features

    @property
    def hs_color(self):
        """Return the hue and saturation color value [float, float]."""
        if not self.supported_features & SUPPORT_COLOR:
            return None
        hue, sat = self._hmdevice.get_hs_color(self._channel)
        return hue * 360.0, sat * 100.0

    @property
    def color_temp(self):
        """Return the color temp in mireds [int]."""
        if not self.supported_features & SUPPORT_COLOR_TEMP:
            return None
        hm_color_temp = self._hmdevice.get_color_temp(self._channel)
        return self.max_mireds - (self.max_mireds - self.min_mireds) * hm_color_temp

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
        if ATTR_TRANSITION in kwargs:
            self._hmdevice.setValue("RAMP_TIME", kwargs[ATTR_TRANSITION], self._channel)

        if ATTR_BRIGHTNESS in kwargs and self._state == "LEVEL":
            percent_bright = float(kwargs[ATTR_BRIGHTNESS]) / 255
            self._hmdevice.set_level(percent_bright, self._channel)
        elif (
            ATTR_HS_COLOR not in kwargs
            and ATTR_COLOR_TEMP not in kwargs
            and ATTR_EFFECT not in kwargs
        ):
            self._hmdevice.on(self._channel)

        if ATTR_HS_COLOR in kwargs and self.supported_features & SUPPORT_COLOR:
            self._hmdevice.set_hs_color(
                hue=kwargs[ATTR_HS_COLOR][0] / 360.0,
                saturation=kwargs[ATTR_HS_COLOR][1] / 100.0,
                channel=self._channel,
            )
        if ATTR_COLOR_TEMP in kwargs:
            hm_temp = (self.max_mireds - kwargs[ATTR_COLOR_TEMP]) / (
                self.max_mireds - self.min_mireds
            )
            self._hmdevice.set_color_temp(hm_temp)
        if ATTR_EFFECT in kwargs:
            self._hmdevice.set_effect(kwargs[ATTR_EFFECT])

    def turn_off(self, **kwargs):
        """Turn the light off."""
        if ATTR_TRANSITION in kwargs:
            self._hmdevice.setValue("RAMP_TIME", kwargs[ATTR_TRANSITION], self._channel)

        self._hmdevice.off(self._channel)

    def _init_data_struct(self):
        """Generate a data dict (self._data) from the Homematic metadata."""
        # Use LEVEL
        self._state = "LEVEL"
        self._data[self._state] = None

        if self.supported_features & SUPPORT_COLOR:
            self._data.update({"COLOR": None})
        if self.supported_features & SUPPORT_EFFECT:
            self._data.update({"PROGRAM": None})
