"""Type definitions for GIOS integration."""
from __future__ import annotations

from typing import Callable, TypedDict


class SensorDescription(TypedDict, total=False):
    """Sensor description class."""

    unit: str
    state_class: str
    value: Callable
