"""Support for ESPHome lights."""
from __future__ import annotations

import logging

from aioesphomeapi import LightInfo, LightState

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_FLASH,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_TRANSITION,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
    COLOR_MODE_ONOFF,
    COLOR_MODE_RGB,
    COLOR_MODE_RGBW,
    COLOR_MODE_RGBWW,
    FLASH_LONG,
    FLASH_SHORT,
    SUPPORT_EFFECT,
    SUPPORT_FLASH,
    SUPPORT_TRANSITION,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import EsphomeEntity, esphome_state_property, platform_async_setup_entry

FLASH_LENGTHS = {FLASH_SHORT: 2, FLASH_LONG: 10}

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up ESPHome lights based on a config entry."""
    await platform_async_setup_entry(
        hass,
        entry,
        async_add_entities,
        component_key="light",
        info_type=LightInfo,
        entity_type=EsphomeLight,
        state_type=LightState,
    )


class EsphomeLight(EsphomeEntity, LightEntity):
    """A switch implementation for ESPHome."""

    @property
    def _static_info(self) -> LightInfo:
        return super()._static_info

    @property
    def _state(self) -> LightState | None:
        return super()._state

    # https://github.com/PyCQA/pylint/issues/3150 for all @esphome_state_property
    # pylint: disable=invalid-overridden-method

    @esphome_state_property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        return self._state.state

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        data = {"key": self._static_info.key, "state": True}
        if ATTR_BRIGHTNESS in kwargs:
            data["brightness"] = kwargs[ATTR_BRIGHTNESS] / 255
        if ATTR_COLOR_TEMP in kwargs:
            data["color_temperature"] = kwargs[ATTR_COLOR_TEMP]
            data["rgb"] = (0, 0, 0)
        if ATTR_RGB_COLOR in kwargs:
            red, green, blue = kwargs[ATTR_RGB_COLOR]
            data["rgb"] = (red / 255, green / 255, blue / 255)
            data["white"] = 0
        if ATTR_RGBW_COLOR in kwargs:
            red, green, blue, white = kwargs[ATTR_RGBW_COLOR]
            data["rgb"] = (red / 255, green / 255, blue / 255)
            data["white"] = white / 255
        if ATTR_RGBWW_COLOR in kwargs:
            red, green, blue, cold_white, warm_white = kwargs[ATTR_RGBWW_COLOR]
            max_mireds = self._static_info.max_mireds
            min_mireds = self._static_info.min_mireds
            mired_range = max_mireds - min_mireds
            try:
                ct_ratio = warm_white / (cold_white + warm_white)
            except ZeroDivisionError:
                ct_ratio = 0.5
            data["color_temperature"] = min_mireds + ct_ratio * mired_range
            data["rgb"] = (red / 255, green / 255, blue / 255)
            data["white"] = max(cold_white, warm_white) / 255
            _LOGGER.debug("async_turn_on: %s -> %s (%s)", {**kwargs}, data, ct_ratio)
        if ATTR_FLASH in kwargs:
            data["flash_length"] = FLASH_LENGTHS[kwargs[ATTR_FLASH]]
        if ATTR_TRANSITION in kwargs:
            data["transition_length"] = kwargs[ATTR_TRANSITION]
        if ATTR_EFFECT in kwargs:
            data["effect"] = kwargs[ATTR_EFFECT]
        await self._client.light_command(**data)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        data = {"key": self._static_info.key, "state": False}
        if ATTR_FLASH in kwargs:
            data["flash_length"] = FLASH_LENGTHS[kwargs[ATTR_FLASH]]
        if ATTR_TRANSITION in kwargs:
            data["transition_length"] = kwargs[ATTR_TRANSITION]
        await self._client.light_command(**data)

    @esphome_state_property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        return round(self._state.brightness * 255)

    @property
    def color_mode(self) -> str | None:
        """Return the color mode of the light."""
        color_modes = self.supported_color_modes
        # RGBWW light may be in color_temp mode or rgbww mode
        if COLOR_MODE_RGBWW in color_modes:
            rgbww = self.rgbww_color
            if not rgbww or rgbww[0] == 0 and rgbww[1] == 0 and rgbww[2] == 0:
                return COLOR_MODE_COLOR_TEMP
            return COLOR_MODE_RGBWW
        # Other light supports a single mode only, return it
        return next(iter(color_modes))

    @esphome_state_property
    def color_temp(self) -> float | None:
        """Return the CT color value in mireds."""
        return self._state.color_temperature

    @esphome_state_property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the RGB color value."""
        red = round(self._state.red * 255)
        green = round(self._state.green * 255)
        blue = round(self._state.blue * 255)
        return (red, green, blue)

    @esphome_state_property
    def rgbw_color(self) -> tuple[int, int, int, int] | None:
        """Return the RGBW color value."""
        red = round(self._state.red * 255)
        green = round(self._state.green * 255)
        blue = round(self._state.blue * 255)
        white = round(self._state.white * 255)
        return (red, green, blue, white)

    @esphome_state_property
    def rgbww_color(self) -> tuple[int, int, int, int, int] | None:
        """Return the RGBWW color value."""
        red = round(self._state.red * 255)
        green = round(self._state.green * 255)
        blue = round(self._state.blue * 255)
        white = self._state.white
        color_temp = self._state.color_temperature

        max_mireds = self._static_info.max_mireds
        min_mireds = self._static_info.min_mireds
        mired_range = max_mireds - min_mireds
        warm_white_fraction = (color_temp - min_mireds) / mired_range
        cold_white_fraction = 1 - warm_white_fraction
        max_cw_ww = max(cold_white_fraction, warm_white_fraction)
        warm_white = int(min(white * warm_white_fraction / max_cw_ww * 255, 255))
        cold_white = int(min(white * cold_white_fraction / max_cw_ww * 255, 255))
        return (red, green, blue, cold_white, warm_white)

    @esphome_state_property
    def effect(self) -> str | None:
        """Return the current effect."""
        return self._state.effect

    @property
    def supported_color_modes(self) -> set | None:
        """Flag supported color_modes."""
        supported_color_modes = set()
        supports_color_temp = self._static_info.supports_color_temperature
        supports_rgb = self._static_info.supports_rgb
        supports_white = self._static_info.supports_white_value
        if supports_rgb and not supports_white and not supports_color_temp:
            supported_color_modes.add(COLOR_MODE_RGB)
        if supports_rgb and supports_white and not supports_color_temp:
            supported_color_modes.add(COLOR_MODE_RGBW)
        if supports_rgb and supports_white and supports_color_temp:
            supported_color_modes.add(COLOR_MODE_RGBWW)
        if supports_color_temp:
            supported_color_modes.add(COLOR_MODE_COLOR_TEMP)
        if not supported_color_modes and self._static_info.supports_brightness:
            supported_color_modes.add(COLOR_MODE_BRIGHTNESS)
        if not supported_color_modes:
            supported_color_modes.add(COLOR_MODE_ONOFF)
        return supported_color_modes

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        flags = SUPPORT_FLASH
        if self._static_info.supports_brightness:
            flags |= SUPPORT_TRANSITION
        if self._static_info.effects:
            flags |= SUPPORT_EFFECT
        return flags

    @property
    def effect_list(self) -> list[str]:
        """Return the list of supported effects."""
        return self._static_info.effects

    @property
    def min_mireds(self) -> float:
        """Return the coldest color_temp that this light supports."""
        return self._static_info.min_mireds

    @property
    def max_mireds(self) -> float:
        """Return the warmest color_temp that this light supports."""
        return self._static_info.max_mireds
