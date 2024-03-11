"""Support for Homematic lights."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import ATTR_DISCOVER_DEVICES
from .entity import HMDevice


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
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
    def color_mode(self) -> ColorMode:
        """Return the color mode of the light."""
        if "COLOR" in self._hmdevice.WRITENODE:
            return ColorMode.HS
        if hasattr(self._hmdevice, "get_color_temp"):
            return ColorMode.COLOR_TEMP
        return ColorMode.BRIGHTNESS

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        """Flag supported color modes."""
        color_modes: set[ColorMode] = set()

        if "COLOR" in self._hmdevice.WRITENODE:
            color_modes.add(ColorMode.HS)
        if hasattr(self._hmdevice, "get_color_temp"):
            color_modes.add(ColorMode.COLOR_TEMP)
        if not color_modes:
            color_modes.add(ColorMode.BRIGHTNESS)

        return color_modes

    @property
    def supported_features(self) -> LightEntityFeature:
        """Flag supported features."""
        features = LightEntityFeature.TRANSITION
        if "PROGRAM" in self._hmdevice.WRITENODE:
            features |= LightEntityFeature.EFFECT
        return features

    @property
    def hs_color(self):
        """Return the hue and saturation color value [float, float]."""
        if ColorMode.HS not in self.supported_color_modes:
            return None
        hue, sat = self._hmdevice.get_hs_color(self._channel)
        return hue * 360.0, sat * 100.0

    @property
    def color_temp(self):
        """Return the color temp in mireds [int]."""
        if ColorMode.COLOR_TEMP not in self.supported_color_modes:
            return None
        hm_color_temp = self._hmdevice.get_color_temp(self._channel)
        return self.max_mireds - (self.max_mireds - self.min_mireds) * hm_color_temp

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        if not self.supported_features & LightEntityFeature.EFFECT:
            return None
        return self._hmdevice.get_effect_list()

    @property
    def effect(self):
        """Return the current color change program of the light."""
        if not self.supported_features & LightEntityFeature.EFFECT:
            return None
        return self._hmdevice.get_effect()

    def turn_on(self, **kwargs: Any) -> None:
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

        if ATTR_HS_COLOR in kwargs:
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

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        if ATTR_TRANSITION in kwargs:
            self._hmdevice.setValue("RAMP_TIME", kwargs[ATTR_TRANSITION], self._channel)

        self._hmdevice.off(self._channel)

    def _init_data_struct(self):
        """Generate a data dict (self._data) from the Homematic metadata."""
        # Use LEVEL
        self._state = "LEVEL"
        self._data[self._state] = None

        if ColorMode.HS in self.supported_color_modes:
            self._data.update({"COLOR": None})
        if self.supported_features & LightEntityFeature.EFFECT:
            self._data.update({"PROGRAM": None})
