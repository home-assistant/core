"""Define Hunter Douglas data models."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from aiopvapi.helpers.aiorequest import AioRequest
from aiopvapi.shades import Shades

from .coordinator import PowerviewShadeUpdateCoordinator


@dataclass
class PowerviewEntryData:
    """Define class for main domain information."""

    api: AioRequest
    room_data: dict[str, Any]
    scene_data: dict[str, Any]
    shades: Any
    shade_data: dict[str, Any]
    coordinator: PowerviewShadeUpdateCoordinator
    device_info: dict[str, Any]


@dataclass
class PowerviewDeviceInfo:
    """Define class for device information."""

    name: str
    mac_address: str
    serial_number: str
    revision: str | None
    firmware: str | None
    model: str
    hub_address: str
