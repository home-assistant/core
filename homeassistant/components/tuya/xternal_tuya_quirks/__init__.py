"""Quirks for Tuya."""

from __future__ import annotations

from .device_quirk import TuyaDeviceQuirk
from .homeassistant import parse_enum
from .registry import QuirksRegistry

__all__ = [
    "TUYA_QUIRKS_REGISTRY",
    "QuirksRegistry",
    "TuyaDeviceQuirk",
    "parse_enum",
]

TUYA_QUIRKS_REGISTRY = QuirksRegistry()
