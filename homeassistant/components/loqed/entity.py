"""Base entity for the LOQED integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LoqedDataCoordinator


class LoqedEntity(CoordinatorEntity[LoqedDataCoordinator]):
    """Defines a LOQED entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: LoqedDataCoordinator) -> None:
        """Initialize the LOQED entity."""
        super().__init__(coordinator=coordinator)

        lock_id = coordinator.lock.id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, lock_id)},
            manufacturer="LOQED",
            name=coordinator.device_name,
            model="Touch Smart Lock",
            connections={(CONNECTION_NETWORK_MAC, lock_id)},
        )
