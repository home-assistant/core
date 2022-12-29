"""Constants for the Canary integration."""
from __future__ import annotations

from collections.abc import ValuesView
from typing import Optional, TypedDict

from canary.model import Entry, Location, Reading


class CanaryData(TypedDict):
    """TypedDict for Canary Coordinator Data."""

    locations: dict[str, Location]
    readings: dict[str, ValuesView[Reading]]
    entries: dict[str, list[Entry]]


SensorTypeItem = tuple[str, Optional[str], Optional[str], Optional[str], list[str]]
