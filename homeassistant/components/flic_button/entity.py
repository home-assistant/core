"""Base entity for Flic Button integration."""

from __future__ import annotations

import logging

from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FlicCoordinator

_LOGGER = logging.getLogger(__name__)


class FlicButtonEntity(CoordinatorEntity[FlicCoordinator]):
    """Base entity for Flic Button integration."""

    _attr_has_entity_name = True
    _unavailable_logged: bool = False

    def __init__(self, coordinator: FlicCoordinator) -> None:
        """Initialize the Flic button entity."""
        super().__init__(coordinator)
        serial = coordinator.serial_number
        if serial:
            device_name = f"{coordinator.model_name} ({serial})"
        else:
            device_name = f"Flic {coordinator.client.address[-5:]}"
        fw = coordinator.firmware_version
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.client.address)},
            connections={(CONNECTION_BLUETOOTH, coordinator.client.address)},
            name=device_name,
            manufacturer="Shortcut Labs",
            model=coordinator.model_name,
            serial_number=serial,
            sw_version=str(fw) if fw is not None else None,
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.coordinator.connected

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        is_available = self.available

        if not is_available and not self._unavailable_logged:
            _LOGGER.info("%s is unavailable", self.coordinator.client.address)
            self._unavailable_logged = True
        elif is_available and self._unavailable_logged:
            _LOGGER.info("%s is back online", self.coordinator.client.address)
            self._unavailable_logged = False

        super()._handle_coordinator_update()
