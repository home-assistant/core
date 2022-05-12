"""Constants for the Canary integration."""
from __future__ import annotations

from collections.abc import ValuesView
from typing import Optional, TypedDict

from canary.model import Entry, Location, SensorType


class CanaryData(TypedDict):
    """TypedDict for Canary Coordinator Data."""

    locations: dict[str, Location]
    readings: dict[str, ValuesView]
    entries: dict[str, list[Entry]]


SensorTypeItem = tuple[
    SensorType, Optional[str], Optional[str], Optional[str], list[str], str
]
