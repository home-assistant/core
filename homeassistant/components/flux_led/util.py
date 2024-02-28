"""Utils for Magic Home."""
from __future__ import annotations

from flux_led.aio import AIOWifiLedBulb
from flux_led.const import COLOR_MODE_DIM as FLUX_COLOR_MODE_DIM, MultiColorEffects

from homeassistant.components.light import ColorMode
from homeassistant.util.color import color_hsv_to_RGB, color_RGB_to_hsv

from .const import FLUX_COLOR_MODE_TO_HASS, MIN_RGB_BRIGHTNESS


def _hass_color_modes(device: AIOWifiLedBulb) -> set[str]:
    color_modes = device.color_modes
    if not color_modes:
        return {ColorMode.ONOFF}
    return {_flux_color_mode_to_hass(mode, color_modes) for mode in color_modes}


def format_as_flux_mac(mac: str | None) -> str | None:
    """Convert a device registry formatted mac to flux mac."""
    return None if mac is None else mac.replace(":", "").upper()


def _human_readable_option(const_option: str) -> str:
    return const_option.replace("_", " ").title()


def mac_matches_by_one(formatted_mac_1: str, formatted_mac_2: str) -> bool:
    """Check if a mac address is only one digit off.

    Some of the devices have two mac addresses which are
    one off from each other. We need to treat them as the same
    since its the same device.
    """
    mac_int_1 = int(formatted_mac_1.replace(":", ""), 16)
    mac_int_2 = int(formatted_mac_2.replace(":", ""), 16)
    return abs(mac_int_1 - mac_int_2) < 2


def _flux_color_mode_to_hass(
    flux_color_mode: str | None, flux_color_modes: set[str]
) -> ColorMode:
    """Map the flux color mode to Home Assistant color mode."""
    if flux_color_mode is None:
        return ColorMode.ONOFF
    if flux_color_mode == FLUX_COLOR_MODE_DIM:
        if len(flux_color_modes) > 1:
            return ColorMode.WHITE
        return ColorMode.BRIGHTNESS
    return FLUX_COLOR_MODE_TO_HASS.get(flux_color_mode, ColorMode.ONOFF)


def _effect_brightness(brightness: int) -> int:
    """Convert hass brightness to effect brightness."""
    return round(brightness / 255 * 100)


def _str_to_multi_color_effect(effect_str: str) -> MultiColorEffects:
    """Convert an multicolor effect string to MultiColorEffects."""
    for effect in MultiColorEffects:
        if effect.name.lower() == effect_str:
            return effect
    # unreachable due to schema validation
    raise RuntimeError  # pragma: no cover


def _is_zero_rgb_brightness(rgb: tuple[int, int, int]) -> bool:
    """RGB brightness is zero."""
    return all(byte == 0 for byte in rgb)


def _min_rgb_brightness(rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    """Ensure the RGB value will not turn off the device from a turn on command."""
    if _is_zero_rgb_brightness(rgb):
        return (MIN_RGB_BRIGHTNESS, MIN_RGB_BRIGHTNESS, MIN_RGB_BRIGHTNESS)
    return rgb


def _min_scaled_rgb_brightness(rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    """Scale an RGB tuple to minimum brightness."""
    return color_hsv_to_RGB(*color_RGB_to_hsv(*rgb)[:2], 1)


def _min_rgbw_brightness(
    rgbw: tuple[int, int, int, int], current_rgbw: tuple[int, int, int, int]
) -> tuple[int, int, int, int]:
    """Ensure the RGBW value will not turn off the device from a turn on command.

    For RGBW, we also need to ensure that there is at least one
    value in the RGB fields or the device will switch to CCT mode unexpectedly.

    If the new value being set is all zeros, scale the current
    color to brightness of 1 so we do not unexpected switch to white
    """
    if _is_zero_rgb_brightness(rgbw[:3]):
        return (*_min_scaled_rgb_brightness(current_rgbw[:3]), rgbw[3])
    return (*_min_rgb_brightness(rgbw[:3]), rgbw[3])


def _min_rgbwc_brightness(
    rgbwc: tuple[int, int, int, int, int], current_rgbwc: tuple[int, int, int, int, int]
) -> tuple[int, int, int, int, int]:
    """Ensure the RGBWC value will not turn off the device from a turn on command.

    For RGBWC, we also need to ensure that there is at least one
    value in the RGB fields or the device will switch to CCT mode unexpectedly

    If the new value being set is all zeros, scale the current
    color to brightness of 1 so we do not unexpected switch to white
    """
    if _is_zero_rgb_brightness(rgbwc[:3]):
        return (*_min_scaled_rgb_brightness(current_rgbwc[:3]), rgbwc[3], rgbwc[4])
    return (*_min_rgb_brightness(rgbwc[:3]), rgbwc[3], rgbwc[4])
