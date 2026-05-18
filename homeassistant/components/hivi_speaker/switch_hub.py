"""Hub for slave-control switches (avoids circular import device_manager <-> switch)."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


class HIVISlaveControlSwitchHub:
    """Hub that tracks all slave-control switch entities for a config entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the switch hub."""
        self.hass = hass
        self.entry = entry
        self.switches: dict[str, Any] = {}

    def get_switch(self, unique_id: str) -> Any:
        """Return a switch entity by its unique ID."""
        return self.switches.get(unique_id)

    def add_switch(self, switch: Any) -> None:
        """Register a switch entity in the hub."""
        self.switches[switch.unique_id] = switch
