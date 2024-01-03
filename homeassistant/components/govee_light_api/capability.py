"""Govee devices capabilities."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.light import ColorMode

GOVEE_COORDINATORS_MAPPER: dict[ColorMode, Callable[..., Any]] = {
    ColorMode.COLOR_TEMP: lambda color: color
}

GOVEE_DEVICE_CAPABILITIES: dict[str, set[ColorMode]] = {
    "H615A": {
        ColorMode.RGB,
        ColorMode.COLOR_TEMP,
        ColorMode.BRIGHTNESS,
    },
    "H619A": {
        ColorMode.RGB,
        ColorMode.COLOR_TEMP,
        ColorMode.BRIGHTNESS,
    },
    "H618A": {
        ColorMode.RGB,
        ColorMode.COLOR_TEMP,
        ColorMode.BRIGHTNESS,
    },
}
