"""Define DataUpdate Coordinator, Base Entity and Device models for Geocaching API."""
from __future__ import annotations

from typing import TypedDict


class GeocachingSensorSettings(TypedDict, total=False):
    """Define Sensor settings class."""

    default_enabled: bool
    device_class: str | None
    icon: str | None
    name: str
    section: str
    state: str
    unit_of_measurement: str | None
