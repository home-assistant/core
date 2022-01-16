"""Utils for Magic Home."""
from __future__ import annotations

from flux_led.aio import AIOWifiLedBulb
from flux_led.const import COLOR_MODE_DIM as FLUX_COLOR_MODE_DIM, MultiColorEffects

from homeassistant.components.light import (
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_ONOFF,
    COLOR_MODE_WHITE,
)

from .const import FLUX_COLOR_MODE_TO_HASS


def _hass_color_modes(device: AIOWifiLedBulb) -> set[str]:
    color_modes = device.color_modes
    return {_flux_color_mode_to_hass(mode, color_modes) for mode in color_modes}


def format_as_flux_mac(mac: str | None) -> str | None:
    """Convert a device registry formatted mac to flux mac."""
    return None if mac is None else mac.replace(":", "").upper()


def _human_readable_option(const_option: str) -> str:
    return const_option.replace("_", " ").title()


def _flux_color_mode_to_hass(
    flux_color_mode: str | None, flux_color_modes: set[str]
) -> str:
    """Map the flux color mode to Home Assistant color mode."""
    if flux_color_mode is None:
        return COLOR_MODE_ONOFF
    if flux_color_mode == FLUX_COLOR_MODE_DIM:
        if len(flux_color_modes) > 1:
            return COLOR_MODE_WHITE
        return COLOR_MODE_BRIGHTNESS
    return FLUX_COLOR_MODE_TO_HASS.get(flux_color_mode, COLOR_MODE_ONOFF)


def _effect_brightness(brightness: int) -> int:
    """Convert hass brightness to effect brightness."""
    return round(brightness / 255 * 100)


def _str_to_multi_color_effect(effect_str: str) -> MultiColorEffects:
    """Convert an multicolor effect string to MultiColorEffects."""
    for effect in MultiColorEffects:
        if effect.name.lower() == effect_str:
            return effect
    # unreachable due to schema validation
    assert False  # pragma: no cover


def _min_rgb_brightness(rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    """Ensure the RGB value will not turn off the device from a turn on command."""
    if all(byte == 0 for byte in rgb):
        return (1, 1, 1)
    return rgb


def _min_rgbw_brightness(rgbw: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """Ensure the RGBW value will not turn off the device from a turn on command."""
    if all(byte == 0 for byte in rgbw):
        return (1, 1, 1, 0)
    return rgbw


def _min_rgbwc_brightness(
    rgbwc: tuple[int, int, int, int, int]
) -> tuple[int, int, int, int, int]:
    """Ensure the RGBWC value will not turn off the device from a turn on command."""
    if all(byte == 0 for byte in rgbwc):
        return (1, 1, 1, 0, 0)
    return rgbwc
