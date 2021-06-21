"""Type definitions for 1-Wire integration."""
from __future__ import annotations

from typing import TypedDict


class DeviceComponentDescription(TypedDict, total=False):
    """Device component description class."""

    path: str
    name: str
    type: str
    default_disabled: bool


class OWServerDeviceDescription(TypedDict):
    """OWServer device description class."""

    path: str
    family: str
    type: str
