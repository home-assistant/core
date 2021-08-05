"""Constants for the Canary integration."""

from __future__ import annotations

from collections.abc import ValuesView
from typing import List, Optional, Tuple, TypedDict

from canary.api import Location


class CanaryData(TypedDict):
    """TypedDict for Canary Coordinator Data."""

    locations: dict[str, Location]
    readings: dict[str, ValuesView]


SensorTypeItem = Tuple[str, Optional[str], Optional[str], Optional[str], List[str]]
