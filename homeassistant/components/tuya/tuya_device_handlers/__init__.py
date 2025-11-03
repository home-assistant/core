"""Tuya device handler."""

from __future__ import annotations

from .registry import QuirksRegistry

__all__ = [
    "TUYA_QUIRKS_REGISTRY",
]

TUYA_QUIRKS_REGISTRY = QuirksRegistry()
