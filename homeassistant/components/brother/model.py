"""Type definitions for Brother integration."""
from __future__ import annotations

from typing import TypedDict


class SensorDescription(TypedDict):
    """Sensor description class."""

    icon: str | None
    label: str
    unit: str | None
    enabled: bool
