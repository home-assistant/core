"""DataUpdateCoordinator for the EARN-E P1 Meter integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from earn_e_p1 import EarnEP1Device, EarnEP1Listener

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

if TYPE_CHECKING:
    from . import EarnEP1ConfigEntry

_LOGGER = logging.getLogger(__name__)


class EarnEP1Coordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for the EARN-E P1 Meter."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: EarnEP1ConfigEntry,
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
        self.serial = serial
        self.identifier = serial
        self.model: str | None = None
        self.sw_version: str | None = None
        self._listener = listener

    def _handle_update(self, device: EarnEP1Device, _raw: dict[str, Any]) -> None:
        """Handle data update from the listener."""
        if self.model != device.model or self.sw_version != device.sw_version:
            self.model = device.model
            self.sw_version = device.sw_version
            device_registry = dr.async_get(self.hass)
            if (
                device_entry := device_registry.async_get_device(
                    identifiers={(DOMAIN, self.identifier)}
                )
            ) is not None:
                device_registry.async_update_device(
                    device_entry.id,
                    model=self.model,
                    sw_version=self.sw_version,
                )
        self.async_set_updated_data(device.data)

    def start(self) -> None:
        """Register with the shared listener."""
        self._listener.register(self.host, self._handle_update)

    def stop(self) -> None:
        """Unregister from the shared listener."""
        self._listener.unregister(self.host)
