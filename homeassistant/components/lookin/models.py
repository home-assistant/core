"""The lookin integration models."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aiolookin import Device, LookInHttpProtocol, LookinUDPSubscriptions

from .coordinator import LookinDataUpdateCoordinator


@dataclass
class LookinData:
    """Data for the lookin integration."""

    host: str
    lookin_udp_subs: LookinUDPSubscriptions
    lookin_device: Device
    meteo_coordinator: LookinDataUpdateCoordinator
    devices: list[dict[str, Any]]
    lookin_protocol: LookInHttpProtocol
    device_coordinators: dict[str, LookinDataUpdateCoordinator]
