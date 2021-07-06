"""Type definitions for Airly integration."""
from __future__ import annotations

from typing import Callable, TypedDict


class SensorDescription(TypedDict, total=False):
    """Sensor description class."""

    device_class: str | None
    icon: str | None
    label: str
    unit: str
    state_class: str | None
    value: Callable
