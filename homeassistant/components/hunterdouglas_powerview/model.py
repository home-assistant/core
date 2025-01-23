"""Define Hunter Douglas data models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from aiopvapi.helpers.aiorequest import AioRequest
from aiopvapi.hub import Hub
from aiopvapi.resources.room import Room
from aiopvapi.resources.scene import Scene
from aiopvapi.resources.shade import BaseShade

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from .coordinator import PowerviewShadeUpdateCoordinator

type PowerviewConfigEntry = ConfigEntry[PowerviewEntryData]


@dataclass(slots=True)
class PowerviewEntryData:
    """Define class for main domain information."""

    api: AioRequest
    room_data: dict[str, Room]
    scene_data: dict[str, Scene]
    shade_data: dict[str, BaseShade]
    coordinator: PowerviewShadeUpdateCoordinator
    device_info: PowerviewDeviceInfo


@dataclass(slots=True)
class PowerviewDeviceInfo:
    """Define class for device information."""

    name: str
    mac_address: str
    serial_number: str
    firmware: str | None
    model: str
    hub_address: str


@dataclass(slots=True)
class PowerviewAPI:
    """Define class to hold the Powerview Hub API data."""

    hub: Hub
    pv_request: AioRequest
    device_info: PowerviewDeviceInfo
