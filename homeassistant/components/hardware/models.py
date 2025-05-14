"""Models for Hardware."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import psutil_home_assistant as ha_psutil

from homeassistant.components import websocket_api
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback


@dataclass
class HardwareData:
    """Hardware data."""

    hardware_platform: dict[str, HardwareProtocol]
    system_status: SystemStatus


@dataclass(slots=True)
class SystemStatus:
    """System status."""

    ha_psutil: ha_psutil
    remove_periodic_timer: CALLBACK_TYPE | None
    subscribers: set[tuple[websocket_api.ActiveConnection, int]]


@dataclass(slots=True)
class BoardInfo:
    """Board info type."""

    hassio_board_id: str | None
    manufacturer: str
    model: str | None
    revision: str | None


@dataclass(slots=True, frozen=True)
class USBInfo:
    """USB info type."""

    vid: str
    pid: str
    serial_number: str | None
    manufacturer: str | None
    description: str | None


@dataclass(slots=True, frozen=True)
class HardwareInfo:
    """Hardware info type."""

    name: str | None
    board: BoardInfo | None
    config_entries: list[str] | None
    dongle: USBInfo | None
    url: str | None


class HardwareProtocol(Protocol):
    """Define the format of hardware platforms."""

    @callback
    def async_info(self, hass: HomeAssistant) -> list[HardwareInfo]:
        """Return info."""
