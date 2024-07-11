"""Define Hunter Douglas data models."""

from __future__ import annotations

from dataclasses import dataclass

from aiopvapi.helpers.aiorequest import AioRequest
from aiopvapi.resources.room import Room
from aiopvapi.resources.scene import Scene
from aiopvapi.resources.shade import BaseShade

from .coordinator import PowerviewShadeUpdateCoordinator


@dataclass
class PowerviewEntryData:
    """Define class for main domain information."""

    api: AioRequest
    room_data: dict[str, Room]
    scene_data: dict[str, Scene]
    shade_data: dict[str, BaseShade]
    coordinator: PowerviewShadeUpdateCoordinator
    device_info: PowerviewDeviceInfo


@dataclass
class PowerviewDeviceInfo:
    """Define class for device information."""

    name: str
    mac_address: str
    serial_number: str
    firmware: str | None
    model: str
    hub_address: str
