"""BleBox light entities implementation."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import blebox_uniapi.light
from blebox_uniapi.light import BleboxColorMode

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import color as color_util

from . import BleBoxConfigEntry
from .entity import BleBoxEntity

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=5)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BleBoxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
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

    _attr_min_color_temp_kelvin = 2700  # 370 Mireds
    _attr_max_color_temp_kelvin = 6500  # 154 Mireds

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
    def color_temp_kelvin(self) -> int:
        """Return the color temperature value in Kelvin."""
        return color_util.color_temperature_mired_to_kelvin(self._feature.color_temp)

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

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""

        rgbw = kwargs.get(ATTR_RGBW_COLOR)
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        effect = kwargs.get(ATTR_EFFECT)
        color_temp_kelvin = kwargs.get(ATTR_COLOR_TEMP_KELVIN)
        rgbww = kwargs.get(ATTR_RGBWW_COLOR)
        feature = self._feature
        value = feature.sensible_on_value
        rgb = kwargs.get(ATTR_RGB_COLOR)

        if rgbw is not None:
            value = list(rgbw)
        if color_temp_kelvin is not None:
            value = feature.return_color_temp_with_brightness(
                int(color_util.color_temperature_kelvin_to_mired(color_temp_kelvin)),
                self.brightness,
            )

        if rgbww is not None:
            value = list(rgbww)

        if rgb is not None:
            if self.color_mode == ColorMode.RGB and brightness is None:
                brightness = self.brightness
            value = list(rgb)

        if brightness is not None:
            if self.color_mode == ColorMode.COLOR_TEMP:
                value = feature.return_color_temp_with_brightness(
                    color_util.color_temperature_kelvin_to_mired(
                        self.color_temp_kelvin
                    ),
                    brightness,
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
