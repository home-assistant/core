"""Quirks for Tuya."""

from __future__ import annotations

from .device_quirk import (
    TuyaClimateDefinition,
    TuyaCoverDefinition,
    TuyaDeviceQuirk,
    TuyaSelectDefinition,
    TuyaSensorDefinition,
    TuyaSwitchDefinition,
)
from .homeassistant import parse_enum
from .registry import QuirksRegistry

__all__ = [
    "TUYA_QUIRKS_REGISTRY",
    "QuirksRegistry",
    "TuyaClimateDefinition",
    "TuyaCoverDefinition",
    "TuyaDeviceQuirk",
    "TuyaSelectDefinition",
    "TuyaSensorDefinition",
    "TuyaSwitchDefinition",
    "parse_enum",
]

TUYA_QUIRKS_REGISTRY = QuirksRegistry()
