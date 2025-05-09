"""Models for Hardware."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from homeassistant.core import HomeAssistant, callback

if TYPE_CHECKING:
    from .websocket_api import SystemStatus


@dataclass
class HardwareData:
    """Hardware data."""

    hardware_platform: dict[str, HardwareProtocol] = None  # type: ignore[assignment]
    system_status: SystemStatus = None  # type: ignore[assignment]


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
