"""Support for Eufy lights."""
from __future__ import annotations

from typing import Any

import lakeside

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.color as color_util
from homeassistant.util.color import (
    color_temperature_kelvin_to_mired as kelvin_to_mired,
    color_temperature_mired_to_kelvin as mired_to_kelvin,
)

EUFY_MAX_KELVIN = 6500
EUFY_MIN_KELVIN = 2700


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up Eufy bulbs."""
    if discovery_info is None:
        return
    add_entities([EufyLight(discovery_info)], True)


class EufyLight(LightEntity):
    """Representation of a Eufy light."""

    def __init__(self, device):
        """Initialize the light."""

        self._temp = None
        self._brightness = None
        self._hs = None
        self._state = None
        self._name = device["name"]
        self._address = device["address"]
        self._code = device["code"]
        self._type = device["type"]
        self._bulb = lakeside.bulb(self._address, self._code, self._type)
        self._colormode = False
        if self._type == "T1011":
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        elif self._type == "T1012":
            self._attr_supported_color_modes = {ColorMode.COLOR_TEMP}
        else:  # T1013
            self._attr_supported_color_modes = {ColorMode.COLOR_TEMP, ColorMode.HS}
        self._bulb.connect()

    def update(self) -> None:
        """Synchronise state from the bulb."""
        self._bulb.update()
        if self._bulb.power:
            self._brightness = self._bulb.brightness
            self._temp = self._bulb.temperature
            if self._bulb.colors:
                self._colormode = True
                self._hs = color_util.color_RGB_to_hs(*self._bulb.colors)
            else:
                self._colormode = False
        self._state = self._bulb.power

    @property
    def unique_id(self):
        """Return the ID of this light."""
        return self._address

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return int(self._brightness * 255 / 100)

    @property
    def min_mireds(self) -> int:
        """Return minimum supported color temperature."""
        return kelvin_to_mired(EUFY_MAX_KELVIN)

    @property
    def max_mireds(self) -> int:
        """Return maximum supported color temperature."""
        return kelvin_to_mired(EUFY_MIN_KELVIN)

    @property
    def color_temp(self):
        """Return the color temperature of this light."""
        temp_in_k = int(
            EUFY_MIN_KELVIN + (self._temp * (EUFY_MAX_KELVIN - EUFY_MIN_KELVIN) / 100)
        )
        return kelvin_to_mired(temp_in_k)

    @property
    def hs_color(self):
        """Return the color of this light."""
        return self._hs

    @property
    def color_mode(self) -> ColorMode:
        """Return the color mode of the light."""
        if self._type == "T1011":
            return ColorMode.BRIGHTNESS
        if self._type == "T1012":
            return ColorMode.COLOR_TEMP
        # T1013
        if not self._colormode:
            return ColorMode.COLOR_TEMP
        return ColorMode.HS

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the specified light on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        colortemp = kwargs.get(ATTR_COLOR_TEMP)
        # pylint: disable=invalid-name
        hs = kwargs.get(ATTR_HS_COLOR)

        if brightness is not None:
            brightness = int(brightness * 100 / 255)
        else:
            if self._brightness is None:
                self._brightness = 100
            brightness = self._brightness

        if colortemp is not None:
            self._colormode = False
            temp_in_k = mired_to_kelvin(colortemp)
            relative_temp = temp_in_k - EUFY_MIN_KELVIN
            temp = int(relative_temp * 100 / (EUFY_MAX_KELVIN - EUFY_MIN_KELVIN))
        else:
            temp = None

        if hs is not None:
            rgb = color_util.color_hsv_to_RGB(hs[0], hs[1], brightness / 255 * 100)
            self._colormode = True
        elif self._colormode:
            rgb = color_util.color_hsv_to_RGB(
                self._hs[0], self._hs[1], brightness / 255 * 100
            )
        else:
            rgb = None

        try:
            self._bulb.set_state(
                power=True, brightness=brightness, temperature=temp, colors=rgb
            )
        except BrokenPipeError:
            self._bulb.connect()
            self._bulb.set_state(
                power=True, brightness=brightness, temperature=temp, colors=rgb
            )

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the specified light off."""
        try:
            self._bulb.set_state(power=False)
        except BrokenPipeError:
            self._bulb.connect()
            self._bulb.set_state(power=False)
