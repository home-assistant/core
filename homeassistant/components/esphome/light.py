"""Support for ESPHome lights."""

from __future__ import annotations

from functools import lru_cache, partial
from typing import TYPE_CHECKING, Any, cast

from aioesphomeapi import (
    APIVersion,
    EntityInfo,
    LightColorCapability,
    LightInfo,
    LightState,
)

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_FLASH,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_TRANSITION,
    ATTR_WHITE,
    FLASH_LONG,
    FLASH_SHORT,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.core import callback

from .entity import (
    EsphomeEntity,
    convert_api_error_ha_error,
    esphome_state_property,
    platform_async_setup_entry,
)

FLASH_LENGTHS = {FLASH_SHORT: 2, FLASH_LONG: 10}


_COLOR_MODE_MAPPING = {
    ColorMode.ONOFF: [
        LightColorCapability.ON_OFF,
    ],
    ColorMode.BRIGHTNESS: [
        LightColorCapability.ON_OFF | LightColorCapability.BRIGHTNESS,
        # for compatibility with older clients (2021.8.x)
        LightColorCapability.BRIGHTNESS,
    ],
    ColorMode.COLOR_TEMP: [
        LightColorCapability.ON_OFF
        | LightColorCapability.BRIGHTNESS
        | LightColorCapability.COLOR_TEMPERATURE,
        LightColorCapability.ON_OFF
        | LightColorCapability.BRIGHTNESS
        | LightColorCapability.COLD_WARM_WHITE,
    ],
    ColorMode.RGB: [
        LightColorCapability.ON_OFF
        | LightColorCapability.BRIGHTNESS
        | LightColorCapability.RGB,
    ],
    ColorMode.RGBW: [
        LightColorCapability.ON_OFF
        | LightColorCapability.BRIGHTNESS
        | LightColorCapability.RGB
        | LightColorCapability.WHITE,
    ],
    ColorMode.RGBWW: [
        LightColorCapability.ON_OFF
        | LightColorCapability.BRIGHTNESS
        | LightColorCapability.RGB
        | LightColorCapability.WHITE
        | LightColorCapability.COLOR_TEMPERATURE,
        LightColorCapability.ON_OFF
        | LightColorCapability.BRIGHTNESS
        | LightColorCapability.RGB
        | LightColorCapability.COLD_WARM_WHITE,
    ],
    ColorMode.WHITE: [
        LightColorCapability.ON_OFF
        | LightColorCapability.BRIGHTNESS
        | LightColorCapability.WHITE
    ],
}


def _mired_to_kelvin(mired_temperature: float) -> int:
    """Convert absolute mired shift to degrees kelvin.

    This function rounds the converted value instead of flooring the value as
    is done in homeassistant.util.color.color_temperature_mired_to_kelvin().

    If the value of mired_temperature is less than or equal to zero, return
    the original value to avoid a divide by zero.
    """
    if mired_temperature <= 0:
        return round(mired_temperature)
    return round(1000000 / mired_temperature)


@lru_cache
def _color_mode_to_ha(mode: int) -> str:
    """Convert an esphome color mode to a HA color mode constant.

    Choses the color mode that best matches the feature-set.
    """
    candidates = []
    for ha_mode, cap_lists in _COLOR_MODE_MAPPING.items():
        for caps in cap_lists:
            if caps == mode:
                # exact match
                return ha_mode
            if (mode & caps) == caps:
                # all requirements met
                candidates.append((ha_mode, caps))

    if not candidates:
        return ColorMode.UNKNOWN

    # choose the color mode with the most bits set
    candidates.sort(key=lambda key: key[1].bit_count())
    return candidates[-1][0]


@lru_cache
def _filter_color_modes(
    supported: list[int], features: LightColorCapability
) -> tuple[int, ...]:
    """Filter the given supported color modes.

    Excluding all values that don't have the requested features.
    """
    features_value = features.value
    return tuple(
        mode for mode in supported if (mode & features_value) == features_value
    )


@lru_cache
def _least_complex_color_mode(color_modes: tuple[int, ...]) -> int:
    """Return the color mode with the least complexity."""
    # popcount with bin() function because it appears
    # to be the best way: https://stackoverflow.com/a/9831671
    color_modes_list = list(color_modes)
    color_modes_list.sort(key=lambda mode: (mode).bit_count())
    return color_modes_list[0]


class EsphomeLight(EsphomeEntity[LightInfo, LightState], LightEntity):
    """A light implementation for ESPHome."""

    _native_supported_color_modes: tuple[int, ...]
    _supports_color_mode = False

    @property
    @esphome_state_property
    def is_on(self) -> bool | None:
        """Return true if the light is on."""
        return self._state.state

    @convert_api_error_ha_error
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        data: dict[str, Any] = {"key": self._key, "state": True}
        # The list of color modes that would fit this service call
        color_modes = self._native_supported_color_modes
        try_keep_current_mode = True

        # rgb/brightness input is in range 0-255, but esphome uses 0-1

        if (brightness_ha := kwargs.get(ATTR_BRIGHTNESS)) is not None:
            data["brightness"] = brightness_ha / 255
            color_modes = _filter_color_modes(
                color_modes, LightColorCapability.BRIGHTNESS
            )

        if (rgb_ha := kwargs.get(ATTR_RGB_COLOR)) is not None:
            rgb = tuple(x / 255 for x in rgb_ha)
            color_bri = max(rgb)
            # normalize rgb
            data["rgb"] = tuple(x / (color_bri or 1) for x in rgb)
            data["color_brightness"] = color_bri
            color_modes = _filter_color_modes(color_modes, LightColorCapability.RGB)
            try_keep_current_mode = False

        if (rgbw_ha := kwargs.get(ATTR_RGBW_COLOR)) is not None:
            *rgb, w = tuple(x / 255 for x in rgbw_ha)  # type: ignore[assignment]
            color_bri = max(rgb)
            # normalize rgb
            data["rgb"] = tuple(x / (color_bri or 1) for x in rgb)
            data["white"] = w
            data["color_brightness"] = color_bri
            color_modes = _filter_color_modes(
                color_modes, LightColorCapability.RGB | LightColorCapability.WHITE
            )
            try_keep_current_mode = False

        if (rgbww_ha := kwargs.get(ATTR_RGBWW_COLOR)) is not None:
            *rgb, cw, ww = tuple(x / 255 for x in rgbww_ha)  # type: ignore[assignment]
            color_bri = max(rgb)
            # normalize rgb
            data["rgb"] = tuple(x / (color_bri or 1) for x in rgb)
            color_modes = _filter_color_modes(color_modes, LightColorCapability.RGB)
            if _filter_color_modes(color_modes, LightColorCapability.COLD_WARM_WHITE):
                # Device supports setting cwww values directly
                data["cold_white"] = cw
                data["warm_white"] = ww
                color_modes = _filter_color_modes(
                    color_modes, LightColorCapability.COLD_WARM_WHITE
                )
            else:
                # need to convert cw+ww part to white+color_temp
                white = data["white"] = max(cw, ww)
                if white != 0:
                    static_info = self._static_info
                    min_ct = static_info.min_mireds
                    max_ct = static_info.max_mireds
                    ct_ratio = ww / (cw + ww)
                    data["color_temperature"] = min_ct + ct_ratio * (max_ct - min_ct)
                color_modes = _filter_color_modes(
                    color_modes,
                    LightColorCapability.COLOR_TEMPERATURE | LightColorCapability.WHITE,
                )
            try_keep_current_mode = False

            data["color_brightness"] = color_bri

        if (flash := kwargs.get(ATTR_FLASH)) is not None:
            data["flash_length"] = FLASH_LENGTHS[flash]

        if (transition := kwargs.get(ATTR_TRANSITION)) is not None:
            data["transition_length"] = transition

        if (color_temp_k := kwargs.get(ATTR_COLOR_TEMP_KELVIN)) is not None:
            # Do not use kelvin_to_mired here to prevent precision loss
            data["color_temperature"] = 1000000.0 / color_temp_k
            if color_temp_modes := _filter_color_modes(
                color_modes, LightColorCapability.COLOR_TEMPERATURE
            ):
                color_modes = color_temp_modes
            else:
                color_modes = _filter_color_modes(
                    color_modes, LightColorCapability.COLD_WARM_WHITE
                )
            try_keep_current_mode = False

        if (effect := kwargs.get(ATTR_EFFECT)) is not None:
            data["effect"] = effect

        if (white_ha := kwargs.get(ATTR_WHITE)) is not None:
            # ESPHome multiplies brightness and white together for final brightness
            # HA only sends `white` in turn_on, and reads total brightness
            # through brightness property.
            data["brightness"] = white_ha / 255
            data["white"] = 1.0
            color_modes = _filter_color_modes(
                color_modes,
                LightColorCapability.BRIGHTNESS | LightColorCapability.WHITE,
            )
            try_keep_current_mode = False

        if self._supports_color_mode and color_modes:
            if (
                try_keep_current_mode
                and self._state is not None
                and self._state.color_mode in color_modes
            ):
                # if possible, stay with the color mode that is already set
                data["color_mode"] = self._state.color_mode
            else:
                # otherwise try the color mode with the least complexity
                # (fewest capabilities set)
                data["color_mode"] = _least_complex_color_mode(color_modes)

        self._client.light_command(**data)

    @convert_api_error_ha_error
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        data: dict[str, Any] = {"key": self._key, "state": False}
        if ATTR_FLASH in kwargs:
            data["flash_length"] = FLASH_LENGTHS[kwargs[ATTR_FLASH]]
        if ATTR_TRANSITION in kwargs:
            data["transition_length"] = kwargs[ATTR_TRANSITION]
        self._client.light_command(**data)

    @property
    @esphome_state_property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        return round(self._state.brightness * 255)

    @property
    @esphome_state_property
    def color_mode(self) -> str | None:
        """Return the color mode of the light."""
        if not self._supports_color_mode:
            supported_color_modes = self.supported_color_modes
            if TYPE_CHECKING:
                assert supported_color_modes is not None
            return next(iter(supported_color_modes))

        return _color_mode_to_ha(self._state.color_mode)

    @property
    @esphome_state_property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the rgb color value [int, int, int]."""
        state = self._state
        if not self._supports_color_mode:
            return (
                round(state.red * 255),
                round(state.green * 255),
                round(state.blue * 255),
            )

        return (
            round(state.red * state.color_brightness * 255),
            round(state.green * state.color_brightness * 255),
            round(state.blue * state.color_brightness * 255),
        )

    @property
    @esphome_state_property
    def rgbw_color(self) -> tuple[int, int, int, int] | None:
        """Return the rgbw color value [int, int, int, int]."""
        white = round(self._state.white * 255)
        rgb = cast("tuple[int, int, int]", self.rgb_color)
        return (*rgb, white)

    @property
    @esphome_state_property
    def rgbww_color(self) -> tuple[int, int, int, int, int] | None:
        """Return the rgbww color value [int, int, int, int, int]."""
        state = self._state
        rgb = cast("tuple[int, int, int]", self.rgb_color)
        if not _filter_color_modes(
            self._native_supported_color_modes, LightColorCapability.COLD_WARM_WHITE
        ):
            # Try to reverse white + color temp to cwww
            static_info = self._static_info
            min_ct = static_info.min_mireds
            max_ct = static_info.max_mireds
            color_temp = min(max(state.color_temperature, min_ct), max_ct)
            white = state.white

            ww_frac = (color_temp - min_ct) / (max_ct - min_ct)
            cw_frac = 1 - ww_frac

            return (
                *rgb,
                round(white * cw_frac / max(cw_frac, ww_frac) * 255),
                round(white * ww_frac / max(cw_frac, ww_frac) * 255),
            )
        return (
            *rgb,
            round(state.cold_white * 255),
            round(state.warm_white * 255),
        )

    @property
    @esphome_state_property
    def color_temp_kelvin(self) -> int:
        """Return the CT color value in Kelvin."""
        return _mired_to_kelvin(self._state.color_temperature)

    @property
    @esphome_state_property
    def effect(self) -> str | None:
        """Return the current effect."""
        return self._state.effect

    @callback
    def _on_static_info_update(self, static_info: EntityInfo) -> None:
        """Set attrs from static info."""
        super()._on_static_info_update(static_info)
        static_info = self._static_info
        self._supports_color_mode = self._api_version >= APIVersion(1, 6)
        self._native_supported_color_modes = tuple(
            static_info.supported_color_modes_compat(self._api_version)
        )
        flags = LightEntityFeature.FLASH

        # All color modes except UNKNOWN,ON_OFF support transition
        modes = self._native_supported_color_modes
        if any(m not in (0, LightColorCapability.ON_OFF) for m in modes):
            flags |= LightEntityFeature.TRANSITION
        if static_info.effects:
            flags |= LightEntityFeature.EFFECT
        self._attr_supported_features = flags

        supported = set(map(_color_mode_to_ha, self._native_supported_color_modes))

        # If we don't know the supported color modes, ESPHome lights
        # are always at least ONOFF so we can safely discard UNKNOWN
        supported.discard(ColorMode.UNKNOWN)

        if ColorMode.ONOFF in supported and len(supported) > 1:
            supported.remove(ColorMode.ONOFF)
        if ColorMode.BRIGHTNESS in supported and len(supported) > 1:
            supported.remove(ColorMode.BRIGHTNESS)
        if ColorMode.WHITE in supported and len(supported) == 1:
            supported.remove(ColorMode.WHITE)

        # If we don't know the supported color modes, its a very old
        # legacy device, and since ESPHome lights are always at least ONOFF
        # we can safely assume that it supports ONOFF
        if not supported:
            supported.add(ColorMode.ONOFF)

        self._attr_supported_color_modes = supported
        self._attr_effect_list = static_info.effects
        self._attr_min_color_temp_kelvin = _mired_to_kelvin(static_info.max_mireds)
        self._attr_max_color_temp_kelvin = _mired_to_kelvin(static_info.min_mireds)


async_setup_entry = partial(
    platform_async_setup_entry,
    info_type=LightInfo,
    entity_type=EsphomeLight,
    state_type=LightState,
)
