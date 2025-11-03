"""Tuya device handler."""

from __future__ import annotations

from .base_quirk import (
    TuyaClimateDefinition,
    TuyaCoverDefinition,
    TuyaDeviceQuirk,
    TuyaSelectDefinition,
    TuyaSensorDefinition,
    TuyaSwitchDefinition,
)
from .registry import QuirksRegistry
from .utils import parse_enum

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
