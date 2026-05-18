"""BleBox light entities implementation."""

from datetime import timedelta
import logging
import math
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

from . import BleBoxConfigEntry
from .const import LIGHT_MAX_KELVINS, LIGHT_MIN_KELVINS
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

    _attr_min_color_temp_kelvin = LIGHT_MIN_KELVINS
    _attr_max_color_temp_kelvin = LIGHT_MAX_KELVINS

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
    def brightness(self) -> int | None:
        """Return the name."""
        return self._feature.brightness

    def _color_temp_to_native_scale(self, x: int) -> int:
        """Convert color temperature from Kelvin to native BleBox scale (0-255).

        BleBox native scale is inverted:
        0=warm (2700K), 255=cold (6500K).
        """
        scaled = (
            (self._attr_max_color_temp_kelvin - x)
            / (self._attr_max_color_temp_kelvin - self._attr_min_color_temp_kelvin)
        ) * 255
        # note: within the operating temperature range here the Kelvin
        # scale has less "integer steps" than the native scale used
        # by blebox devices. Thus we need to use rounding method that is opposite
        # to the one used in _color_temp_from_native_scale in order to avoid
        # temperature value jumping by one step when the temperature value is read
        # back from the device
        bounded = max(min(math.floor(scaled), 255), 0)
        return int(bounded)

    def _color_temp_from_native_scale(self, x: int) -> int:
        """Convert color temperature from native BleBox scale (0-255) to Kelvin.

        BleBox native scale is inverted:
        0=warm (2700K), 255=cold (6500K).
        """
        scaled = self._attr_max_color_temp_kelvin - (x / 255) * (
            self._attr_max_color_temp_kelvin - self._attr_min_color_temp_kelvin
        )
        # note: see _color_temp_to_native_scale for explanation of rounding method
        bounded = max(
            min(math.ceil(scaled), self._attr_max_color_temp_kelvin),
            self._attr_min_color_temp_kelvin,
        )
        return int(bounded)

    @property
    def color_temp_kelvin(self) -> int:
        """Return the color temperature value in Kelvin."""
        return self._color_temp_from_native_scale(self._feature.color_temp)

    @property
    def color_mode(self) -> ColorMode:
        """Return the color mode.

        Set values to _attr_ibutes if needed.
        """
        return COLOR_MODE_MAP.get(self._feature.color_mode, ColorMode.ONOFF)

    @property
    def supported_color_modes(self) -> set[ColorMode]:
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
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return value for rgb."""
        if (rgb_hex := self._feature.rgb_hex) is None:
            return None
        return tuple(
            blebox_uniapi.light.Light.normalise_elements_of_rgb(
                blebox_uniapi.light.Light.rgb_hex_to_rgb_list(rgb_hex)[0:3]
            )
        )

    @property
    def rgbw_color(self) -> tuple[int, int, int, int] | None:
        """Return the hue and saturation."""
        if (rgbw_hex := self._feature.rgbw_hex) is None:
            return None
        return tuple(blebox_uniapi.light.Light.rgb_hex_to_rgb_list(rgbw_hex)[0:4])

    @property
    def rgbww_color(self) -> tuple[int, int, int, int, int] | None:
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
        rgb = kwargs.get(ATTR_RGB_COLOR)

        feature = self._feature
        value = feature.sensible_on_value

        if rgbw is not None:
            value = list(rgbw)
        if color_temp_kelvin is not None:
            value = feature.return_color_temp_with_brightness(
                self._color_temp_to_native_scale(color_temp_kelvin),
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
                    self._color_temp_to_native_scale(self.color_temp_kelvin),
                    brightness,
                )
            else:
                value = feature.apply_brightness(value, brightness)

        if isinstance(value, (list, tuple)) and not any(value):
            await self._feature.async_off()
            return

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
