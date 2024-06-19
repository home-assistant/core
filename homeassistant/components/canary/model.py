"""Constants for the Canary integration."""

from __future__ import annotations

from collections.abc import ValuesView
from typing import TypedDict

from canary.model import Location, Reading


class CanaryData(TypedDict):
    """TypedDict for Canary Coordinator Data."""

    locations: dict[str, Location]
    readings: dict[str, ValuesView[Reading]]
