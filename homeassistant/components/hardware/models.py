"""Models for Hardware."""
from __future__ import annotations

from typing import Protocol, TypedDict

from homeassistant.core import HomeAssistant, callback


class HardwareInfo(TypedDict):
    """Board info type."""

    image: str | None
    name: str | None
    type: str
    url: str | None


class HardwareProtocol(Protocol):
    """Define the format of hardware platforms."""

    @callback
    def async_info(self, hass: HomeAssistant) -> HardwareInfo:
        """Return info."""
