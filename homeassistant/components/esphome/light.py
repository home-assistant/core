"""Support for ESPHome lights."""
from __future__ import annotations

from typing import Any, cast

from aioesphomeapi import APIVersion, LightColorMode, LightInfo, LightState

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_FLASH,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_TRANSITION,
    ATTR_WHITE,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
    COLOR_MODE_ONOFF,
    COLOR_MODE_RGB,
    COLOR_MODE_RGBW,
    COLOR_MODE_RGBWW,
    COLOR_MODE_UNKNOWN,
    COLOR_MODE_WHITE,
    FLASH_LONG,
    FLASH_SHORT,
    SUPPORT_EFFECT,
    SUPPORT_FLASH,
    SUPPORT_TRANSITION,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import (
    EsphomeEntity,
    EsphomeEnumMapper,
    esphome_state_property,
    platform_async_setup_entry,
)

FLASH_LENGTHS = {FLASH_SHORT: 2, FLASH_LONG: 10}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
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


_COLOR_MODES: EsphomeEnumMapper[LightColorMode, str] = EsphomeEnumMapper(
    {
        LightColorMode.UNKNOWN: COLOR_MODE_UNKNOWN,
        LightColorMode.ON_OFF: COLOR_MODE_ONOFF,
        LightColorMode.BRIGHTNESS: COLOR_MODE_BRIGHTNESS,
        LightColorMode.WHITE: COLOR_MODE_WHITE,
        LightColorMode.COLOR_TEMPERATURE: COLOR_MODE_COLOR_TEMP,
        LightColorMode.COLD_WARM_WHITE: COLOR_MODE_COLOR_TEMP,
        LightColorMode.RGB: COLOR_MODE_RGB,
        LightColorMode.RGB_WHITE: COLOR_MODE_RGBW,
        LightColorMode.RGB_COLOR_TEMPERATURE: COLOR_MODE_RGBWW,
        LightColorMode.RGB_COLD_WARM_WHITE: COLOR_MODE_RGBWW,
    }
)


# https://github.com/PyCQA/pylint/issues/3150 for all @esphome_state_property
# pylint: disable=invalid-overridden-method


class EsphomeLight(EsphomeEntity[LightInfo, LightState], LightEntity):
    """A light implementation for ESPHome."""

    @property
    def _supports_color_mode(self) -> bool:
        """Return whether the client supports the new color mode system natively."""
        return self._api_version >= APIVersion(1, 6)

    @esphome_state_property
    def is_on(self) -> bool | None:  # type: ignore[override]
        """Return true if the light is on."""
        return self._state.state

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        data: dict[str, Any] = {"key": self._static_info.key, "state": True}
        # rgb/brightness input is in range 0-255, but esphome uses 0-1

        if (brightness_ha := kwargs.get(ATTR_BRIGHTNESS)) is not None:
            data["brightness"] = brightness_ha / 255

        if (rgb_ha := kwargs.get(ATTR_RGB_COLOR)) is not None:
            rgb = tuple(x / 255 for x in rgb_ha)
            color_bri = max(rgb)
            # normalize rgb
            data["rgb"] = tuple(x / (color_bri or 1) for x in rgb)
            data["color_brightness"] = color_bri
            if self._supports_color_mode:
                data["color_mode"] = LightColorMode.RGB

        if (rgbw_ha := kwargs.get(ATTR_RGBW_COLOR)) is not None:
            # pylint: disable=invalid-name
            *rgb, w = tuple(x / 255 for x in rgbw_ha)  # type: ignore[assignment]
            color_bri = max(rgb)
            # normalize rgb
            data["rgb"] = tuple(x / (color_bri or 1) for x in rgb)
            data["white"] = w
            data["color_brightness"] = color_bri
            if self._supports_color_mode:
                data["color_mode"] = LightColorMode.RGB_WHITE

        if (rgbww_ha := kwargs.get(ATTR_RGBWW_COLOR)) is not None:
            # pylint: disable=invalid-name
            *rgb, cw, ww = tuple(x / 255 for x in rgbww_ha)  # type: ignore[assignment]
            color_bri = max(rgb)
            # normalize rgb
            data["rgb"] = tuple(x / (color_bri or 1) for x in rgb)
            modes = self._native_supported_color_modes
            if (
                self._supports_color_mode
                and LightColorMode.RGB_COLD_WARM_WHITE in modes
            ):
                data["cold_white"] = cw
                data["warm_white"] = ww
                target_mode = LightColorMode.RGB_COLD_WARM_WHITE
            else:
                # need to convert cw+ww part to white+color_temp
                white = data["white"] = max(cw, ww)
                if white != 0:
                    min_ct = self.min_mireds
                    max_ct = self.max_mireds
                    ct_ratio = ww / (cw + ww)
                    data["color_temperature"] = min_ct + ct_ratio * (max_ct - min_ct)
                target_mode = LightColorMode.RGB_COLOR_TEMPERATURE

            data["color_brightness"] = color_bri
            if self._supports_color_mode:
                data["color_mode"] = target_mode

        if (flash := kwargs.get(ATTR_FLASH)) is not None:
            data["flash_length"] = FLASH_LENGTHS[flash]

        if (transition := kwargs.get(ATTR_TRANSITION)) is not None:
            data["transition_length"] = transition

        if (color_temp := kwargs.get(ATTR_COLOR_TEMP)) is not None:
            data["color_temperature"] = color_temp
            if self._supports_color_mode:
                data["color_mode"] = LightColorMode.COLOR_TEMPERATURE

        if (effect := kwargs.get(ATTR_EFFECT)) is not None:
            data["effect"] = effect

        if (white_ha := kwargs.get(ATTR_WHITE)) is not None:
            # ESPHome multiplies brightness and white together for final brightness
            # HA only sends `white` in turn_on, and reads total brightness through brightness property
            data["brightness"] = white_ha / 255
            data["white"] = 1.0
            data["color_mode"] = LightColorMode.WHITE

        await self._client.light_command(**data)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        data: dict[str, Any] = {"key": self._static_info.key, "state": False}
        if ATTR_FLASH in kwargs:
            data["flash_length"] = FLASH_LENGTHS[kwargs[ATTR_FLASH]]
        if ATTR_TRANSITION in kwargs:
            data["transition_length"] = kwargs[ATTR_TRANSITION]
        await self._client.light_command(**data)

    @esphome_state_property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        return round(self._state.brightness * 255)

    @esphome_state_property
    def color_mode(self) -> str | None:
        """Return the color mode of the light."""
        if not self._supports_color_mode:
            supported = self.supported_color_modes
            if not supported:
                return None
            return next(iter(supported))

        return _COLOR_MODES.from_esphome(self._state.color_mode)

    @esphome_state_property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the rgb color value [int, int, int]."""
        if not self._supports_color_mode:
            return (
                round(self._state.red * 255),
                round(self._state.green * 255),
                round(self._state.blue * 255),
            )

        return (
            round(self._state.red * self._state.color_brightness * 255),
            round(self._state.green * self._state.color_brightness * 255),
            round(self._state.blue * self._state.color_brightness * 255),
        )

    @esphome_state_property
    def rgbw_color(self) -> tuple[int, int, int, int] | None:
        """Return the rgbw color value [int, int, int, int]."""
        white = round(self._state.white * 255)
        rgb = cast("tuple[int, int, int]", self.rgb_color)
        return (*rgb, white)

    @esphome_state_property
    def rgbww_color(self) -> tuple[int, int, int, int, int] | None:
        """Return the rgbww color value [int, int, int, int, int]."""
        rgb = cast("tuple[int, int, int]", self.rgb_color)
        if (
            not self._supports_color_mode
            or self._state.color_mode != LightColorMode.RGB_COLD_WARM_WHITE
        ):
            # Try to reverse white + color temp to cwww
            min_ct = self._static_info.min_mireds
            max_ct = self._static_info.max_mireds
            color_temp = min(max(self._state.color_temperature, min_ct), max_ct)
            white = self._state.white

            ww_frac = (color_temp - min_ct) / (max_ct - min_ct)
            cw_frac = 1 - ww_frac

            return (
                *rgb,
                round(white * cw_frac / max(cw_frac, ww_frac) * 255),
                round(white * ww_frac / max(cw_frac, ww_frac) * 255),
            )
        return (
            *rgb,
            round(self._state.cold_white * 255),
            round(self._state.warm_white * 255),
        )

    @esphome_state_property
    def color_temp(self) -> float | None:  # type: ignore[override]
        """Return the CT color value in mireds."""
        return self._state.color_temperature

    @esphome_state_property
    def effect(self) -> str | None:
        """Return the current effect."""
        return self._state.effect

    @property
    def _native_supported_color_modes(self) -> list[LightColorMode]:
        return self._static_info.supported_color_modes_compat(self._api_version)

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        flags = SUPPORT_FLASH

        # All color modes except UNKNOWN,ON_OFF support transition
        modes = self._native_supported_color_modes
        if any(m not in (LightColorMode.UNKNOWN, LightColorMode.ON_OFF) for m in modes):
            flags |= SUPPORT_TRANSITION
        if self._static_info.effects:
            flags |= SUPPORT_EFFECT
        return flags

    @property
    def supported_color_modes(self) -> set[str] | None:
        """Flag supported color modes."""
        return set(map(_COLOR_MODES.from_esphome, self._native_supported_color_modes))

    @property
    def effect_list(self) -> list[str]:
        """Return the list of supported effects."""
        return self._static_info.effects

    @property
    def min_mireds(self) -> float:  # type: ignore[override]
        """Return the coldest color_temp that this light supports."""
        return self._static_info.min_mireds

    @property
    def max_mireds(self) -> float:  # type: ignore[override]
        """Return the warmest color_temp that this light supports."""
        return self._static_info.max_mireds
