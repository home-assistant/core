"""BleBox light entities implementation."""

from __future__ import annotations

from datetime import timedelta
import logging
import math
from typing import Any

import blebox_uniapi.light
from blebox_uniapi.light import BleboxColorMode

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BleBoxConfigEntry
from .const import LIGHT_MAX_MIREDS, LIGHT_MIN_MIREDS
from .entity import BleBoxEntity

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=5)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BleBoxConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a BleBox entry."""
    entities = [
        BleBoxLightEntity(feature)
        for feature in config_entry.runtime_data.features.get("lights", [])
    ]
    async_add_entities(entities, True)


COLOR_MODE_MAP = {
    BleboxColorMode.RGBW: ColorMode.RGBW,
    BleboxColorMode.RGB: ColorMode.RGB,
    BleboxColorMode.MONO: ColorMode.BRIGHTNESS,
    BleboxColorMode.RGBorW: ColorMode.RGBW,  # white hex is prioritised over RGB channel
    BleboxColorMode.CT: ColorMode.COLOR_TEMP,
    BleboxColorMode.CTx2: ColorMode.COLOR_TEMP,  # two instances
    BleboxColorMode.RGBWW: ColorMode.RGBWW,
}


class BleBoxLightEntity(BleBoxEntity[blebox_uniapi.light.Light], LightEntity):
    """Representation of BleBox lights."""

    _attr_max_mireds = LIGHT_MAX_MIREDS
    _attr_min_mireds = LIGHT_MIN_MIREDS

    def __init__(self, feature: blebox_uniapi.light.Light) -> None:
        """Initialize a BleBox light."""
        super().__init__(feature)
        if feature.effect_list:
            self._attr_supported_features = LightEntityFeature.EFFECT

    @property
    def is_on(self) -> bool:
        """Return if light is on."""
        return self._feature.is_on

    @property
    def brightness(self):
        """Return the name."""
        return self._feature.brightness

    @property
    def color_temp(self):
        """Return color temperature."""
        return self._color_temp_from_native_scale(self._feature.color_temp)

    @property
    def color_mode(self):
        """Return the color mode.

        Set values to _attr_ibutes if needed.
        """
        return COLOR_MODE_MAP.get(self._feature.color_mode, ColorMode.ONOFF)

    @property
    def supported_color_modes(self):
        """Return supported color modes."""
        return {self.color_mode}

    @property
    def effect_list(self) -> list[str]:
        """Return the list of supported effects."""
        return self._feature.effect_list

    @property
    def effect(self) -> str | None:
        """Return the current effect."""
        return self._feature.effect

    @property
    def rgb_color(self):
        """Return value for rgb."""
        if (rgb_hex := self._feature.rgb_hex) is None:
            return None
        return tuple(
            blebox_uniapi.light.Light.normalise_elements_of_rgb(
                blebox_uniapi.light.Light.rgb_hex_to_rgb_list(rgb_hex)[0:3]
            )
        )

    @property
    def rgbw_color(self):
        """Return the hue and saturation."""
        if (rgbw_hex := self._feature.rgbw_hex) is None:
            return None
        return tuple(blebox_uniapi.light.Light.rgb_hex_to_rgb_list(rgbw_hex)[0:4])

    @property
    def rgbww_color(self):
        """Return value for rgbww."""
        if (rgbww_hex := self._feature.rgbww_hex) is None:
            return None
        return tuple(blebox_uniapi.light.Light.rgb_hex_to_rgb_list(rgbww_hex))

    def _color_temp_to_native_scale(self, x):
        """Convert color temperature from mireds to native Blebox temperature scale."""
        scaled = ((x - self.min_mireds) / (self.max_mireds - self.min_mireds)) * 255
        # note: within the operating temperature range here the mired
        # scale has less "integer steps" (~216) than the native scale used
        # by blebox devices. Thus we need to use rounding method that is opposite
        # to the one used in _color_temp_from_native_scale in order to avoid
        # temperature value jumping by one step when the temparatur value is read
        # back from the device
        bounded = max(min(math.floor(scaled), 255), 0)
        return int(bounded)

    def _color_temp_from_native_scale(self, x):
        """Convert color temperature from native Blebox temperature scale to mireds."""
        scaled = (x / 255) * (self.max_mireds - self.min_mireds) + self.min_mireds
        # note: see _color_temp_to_native_scale for explanation of rounding method
        bounded = max(min(math.ceil(scaled), self.max_mireds), self.min_mireds)
        return int(bounded)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        rgbw = kwargs.get(ATTR_RGBW_COLOR)
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        effect = kwargs.get(ATTR_EFFECT)
        color_temp = kwargs.get(ATTR_COLOR_TEMP)
        rgbww = kwargs.get(ATTR_RGBWW_COLOR)
        rgb = kwargs.get(ATTR_RGB_COLOR)

        feature = self._feature
        value = feature.sensible_on_value

        if rgbw is not None:
            value = list(rgbw)

        if color_temp is not None:
            value = feature.return_color_temp_with_brightness(
                self._color_temp_to_native_scale(color_temp), self.brightness
            )

        if rgbww is not None:
            value = list(rgbww)

        if rgb is not None:
            if self.color_mode == ColorMode.RGB and brightness is None:
                brightness = self.brightness
            value = list(rgb)

        if brightness is not None:
            if self.color_mode == ATTR_COLOR_TEMP:
                value = feature.return_color_temp_with_brightness(
                    self.color_temp, brightness
                )
            else:
                value = feature.apply_brightness(value, brightness)

        try:
            await self._feature.async_on(value)
        except ValueError as exc:
            raise ValueError(
                f"Turning on '{self.name}' failed: Bad value {value}"
            ) from exc

        if effect is not None:
            try:
                effect_value = self.effect_list.index(effect)
                await self._feature.async_api_command("effect", effect_value)
            except ValueError as exc:
                raise ValueError(
                    f"Turning on with effect '{self.name}' failed: {effect} not in"
                    " effect list."
                ) from exc

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._feature.async_off()
