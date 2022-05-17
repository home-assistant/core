"""Models for Hardware."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from homeassistant.core import HomeAssistant, callback


@dataclass
class HardwareInfo:
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
