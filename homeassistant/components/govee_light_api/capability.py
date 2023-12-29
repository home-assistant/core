"""Govee devices capabilities."""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum, auto
from typing import Any


class GoveeLightCapabilities(Enum):
    """Govee Lights capabilities."""

    COLOR_RGB = auto()
    COLOR_KELVIN_TEMPERATURE = auto()
    BRIGHTNESS = auto()


GOVEE_COORDINATORS_MAPPER: dict[GoveeLightCapabilities, Callable[..., Any]] = {
    GoveeLightCapabilities.COLOR_KELVIN_TEMPERATURE: lambda color: color
}

GOVEE_DEVICE_CAPABILITIES: dict[str, set[GoveeLightCapabilities]] = {
    "H615A": {
        GoveeLightCapabilities.COLOR_RGB,
        GoveeLightCapabilities.COLOR_KELVIN_TEMPERATURE,
        GoveeLightCapabilities.BRIGHTNESS,
    },
    "H619A": {
        GoveeLightCapabilities.COLOR_RGB,
        GoveeLightCapabilities.COLOR_KELVIN_TEMPERATURE,
        GoveeLightCapabilities.BRIGHTNESS,
    },
    "H618A": {
        GoveeLightCapabilities.COLOR_RGB,
        GoveeLightCapabilities.COLOR_KELVIN_TEMPERATURE,
        GoveeLightCapabilities.BRIGHTNESS,
    },
}
