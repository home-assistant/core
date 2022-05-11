"""Models for Hardware."""
from __future__ import annotations

from typing import Protocol, TypedDict

from homeassistant.core import callback


class BoardInfo(TypedDict):
    """Board info type."""

    image: str | None
    name: str | None
    url: str | None


class HardwareProtocol(Protocol):
    """Define the format of hardware platforms."""

    @callback
    def async_board_info(self) -> BoardInfo:
        """Return board info."""
