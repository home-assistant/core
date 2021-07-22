"""Type definitions for Brother integration."""
from __future__ import annotations

from typing import NamedTuple


class BrotherSensorMetadata(NamedTuple):
    """Metadata for an individual Brother sensor."""

    icon: str | None
    label: str
    unit_of_measurement: str | None
    enabled: bool
    state_class: str | None = None
    device_class: str | None = None
