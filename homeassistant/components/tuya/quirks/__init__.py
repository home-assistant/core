"""Quirks for Tuya."""

from __future__ import annotations

from .device_quirk import TuyaCoverDefinition, TuyaCoverDeviceClass, TuyaDeviceQuirk
from .homeassistant import parse_enum
from .registry import QuirksRegistry

__all__ = [
    "QUIRKS_REGISTRY",
    "QuirksRegistry",
    "TuyaCoverDefinition",
    "TuyaCoverDeviceClass",
    "TuyaDeviceQuirk",
    "parse_enum",
]

TUYA_QUIRKS_REGISTRY = QuirksRegistry()
