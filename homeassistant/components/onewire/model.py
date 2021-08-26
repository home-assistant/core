"""Type definitions for 1-Wire integration."""
from __future__ import annotations

from typing import TypedDict


class OWServerDeviceDescription(TypedDict):
    """OWServer device description class."""

    path: str
    family: str
    type: str
