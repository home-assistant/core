"""Device representation for Redgtech integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RedgtechDevice:
    """Representation of a Redgtech device."""

    id: str
    name: str
    type: str
    state: bool
    model: str | None = None
    version: str | None = None

    def __init__(self, data: dict[str, Any]) -> None:
        """Initialize device from API data."""
        self.id = data.get("endpointId", "")
        self.name = data.get("friendlyName", "")
        self.type = data.get("type", "switch")
        self.state = data.get("value", False)
        self.model = data.get("model")
        self.version = data.get("version")

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this device."""
        return self.id
