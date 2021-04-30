"""Type definitions for Airly integration."""
from __future__ import annotations

from typing import TypedDict


class SensorDescription(TypedDict):
    """Sensor description class."""

    device_class: str | None
    icon: str | None
    label: str
    unit: str
