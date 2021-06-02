"""Type definitions for Nettig Air Monitor integration."""
from __future__ import annotations

from typing import TypedDict


class SensorDescription(TypedDict):
    """Sensor description class."""

    label: str
    unit: str | None
    device_class: str | None
    icon: str | None
    enabled: bool
    state_class: str | None
