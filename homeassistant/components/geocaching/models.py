"""Define DataUpdate Coordinator, Base Entity and Device models for Geocaching API."""
from __future__ import annotations

from typing import TypedDict


class GeocachingSensorSettings(TypedDict):
    """Define Sensor settings class."""

    name: str
    section: str
    state: str
    unit_of_measurement: str | None
    device_class: str | None
    icon: str
    default_enabled: bool
