"""The lookin integration models."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable

from aiolookin import Device, LookInHttpProtocol, LookinUDPSubscriptions

from .coordinator import LookinDataUpdateCoordinator


@dataclass
class LookinData:
    """Data for the lookin integration."""

    lookin_udp_subs: LookinUDPSubscriptions
    lookin_device: Device
    meteo_coordinator: LookinDataUpdateCoordinator
    devices: list[dict[str, Any]]
    lookin_protocol: LookInHttpProtocol
    device_coordinators: dict[str, LookinDataUpdateCoordinator]


class LookinUDPManager:
    """Manage the lookin UDP subscriptions."""

    def __init__(self) -> None:
        """Init the manager."""
        self.lock = asyncio.Lock()
        self.listener: Callable | None = None
        self.subscriptions: LookinUDPSubscriptions | None = None
