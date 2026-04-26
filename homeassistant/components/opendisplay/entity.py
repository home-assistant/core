"""Base entity for OpenDisplay devices."""

from __future__ import annotations

from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothCoordinatorEntity,
)
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity import EntityDescription

from .coordinator import OpenDisplayCoordinator


class OpenDisplayEntity(PassiveBluetoothCoordinatorEntity[OpenDisplayCoordinator]):
    """Base class for all OpenDisplay entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: OpenDisplayCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.address}-{description.key}"

        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, coordinator.address)},
        )
