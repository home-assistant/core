"""Models helper class for the Ambee integration."""
from __future__ import annotations

from typing import TypedDict


class AmbeeSensor(TypedDict, total=False):
    """Represent an Ambee Sensor."""

    device_class: str
    enabled_by_default: bool
    icon: str
    name: str
    state_class: str
    unit_of_measurement: str
