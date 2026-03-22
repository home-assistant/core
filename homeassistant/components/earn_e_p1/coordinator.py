"""DataUpdateCoordinator for the EARN-E P1 Meter integration."""

from __future__ import annotations

import logging
from typing import Any

from earn_e_p1 import EarnEP1Device, EarnEP1Listener
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class EarnEP1Coordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for the EARN-E P1 Meter."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        host: str,
        serial: str,
        listener: EarnEP1Listener,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
        )
        self.host = host
        self.data = {}
        self.serial = serial
        self.identifier = serial
        self.model: str | None = None
        self.sw_version: str | None = None
        self._listener = listener

    def _handle_update(self, device: EarnEP1Device, raw: dict[str, Any]) -> None:
        """Handle data update from the listener."""
        self.model = device.model
        self.sw_version = device.sw_version
        self.async_set_updated_data(device.data)

    def start(self) -> None:
        """Register with the shared listener."""
        self._listener.register(self.host, self._handle_update)

    def stop(self) -> None:
        """Unregister from the shared listener."""
        self._listener.unregister(self.host)
