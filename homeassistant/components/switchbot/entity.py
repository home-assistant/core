"""An abstract class common to all Switchbot entities."""
from __future__ import annotations

from homeassistant.helpers.entity import Entity


class SwitchbotEntity(Entity):
    """Generic entity encapsulating common features of Switchbot device."""

    def __init__(self, mac_address: str, last_ran: bool | None) -> None:
        """Initialize the entity."""
        super().__init__()
        self._last_run_success = last_ran
        self._mac = mac_address

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
        return {"last_run_success": self._last_run_success, "mac_address": self._mac}
