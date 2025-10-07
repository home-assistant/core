"""Quirks for Tuya."""

from __future__ import annotations

from .device_quirk import (
    TuyaCoverDefinition,
    TuyaDeviceQuirk,
    TuyaSelectDefinition,
    TuyaSensorDefinition,
)
from .homeassistant import (
    TuyaCoverDeviceClass,
    TuyaEntityCategory,
    TuyaSensorDeviceClass,
    parse_enum,
)
from .registry import QuirksRegistry

__all__ = [
    "TUYA_QUIRKS_REGISTRY",
    "QuirksRegistry",
    "TuyaCoverDefinition",
    "TuyaCoverDeviceClass",
    "TuyaDeviceQuirk",
    "TuyaEntityCategory",
    "TuyaSelectDefinition",
    "TuyaSensorDefinition",
    "TuyaSensorDeviceClass",
    "parse_enum",
]

TUYA_QUIRKS_REGISTRY = QuirksRegistry()
