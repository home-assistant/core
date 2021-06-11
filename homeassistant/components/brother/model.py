"""Type definitions for Brother integration."""
from __future__ import annotations

from typing import TypedDict


class SensorDescription(TypedDict, total=False):
    """Sensor description class."""

    icon: str | None
    label: str
    unit: str | None
    enabled: bool
    state_class: str | None
    device_class: str | None
