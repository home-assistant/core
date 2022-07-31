"""Constants for the Canary integration."""
from __future__ import annotations

from collections.abc import ValuesView
from typing import Optional, TypedDict

from canary.model import Location


class CanaryData(TypedDict):
    """TypedDict for Canary Coordinator Data."""

    locations: dict[str, Location]
    readings: dict[str, ValuesView]


SensorTypeItem = tuple[str, Optional[str], Optional[str], Optional[str], list[str]]
