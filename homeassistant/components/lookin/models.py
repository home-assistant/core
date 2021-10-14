"""The lookin integration models."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .aiolookin import Device, LookInHttpProtocol, LookinUDPSubscriptions


@dataclass
class LookinData:
    """Data for the lookin integration."""

    lookin_udp_subs: LookinUDPSubscriptions
    lookin_device: Device
    meteo_coordinator: DataUpdateCoordinator
    devices: list[dict[str, Any]]
    lookin_protocol: LookInHttpProtocol
