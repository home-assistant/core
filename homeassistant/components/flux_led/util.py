"""Utils for FluxLED/MagicHome."""
from __future__ import annotations

from flux_led.aio import AIOWifiLedBulb
from flux_led.const import COLOR_MODE_DIM as FLUX_COLOR_MODE_DIM

from homeassistant.components.light import (
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_ONOFF,
    COLOR_MODE_WHITE,
)

from .const import FLUX_COLOR_MODE_TO_HASS


def _hass_color_modes(device: AIOWifiLedBulb) -> set[str]:
    color_modes = device.color_modes
    return {_flux_color_mode_to_hass(mode, color_modes) for mode in color_modes}


def _flux_color_mode_to_hass(flux_color_mode: str, flux_color_modes: set[str]) -> str:
    """Map the flux color mode to Home Assistant color mode."""
    if flux_color_mode == FLUX_COLOR_MODE_DIM:
        if len(flux_color_modes) > 1:
            return COLOR_MODE_WHITE
        return COLOR_MODE_BRIGHTNESS
    return FLUX_COLOR_MODE_TO_HASS.get(flux_color_mode, COLOR_MODE_ONOFF)
