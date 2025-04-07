"""Provides the DataUpdateCoordinator."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import GardenaBluetoothCoordinator


class GardenaBluetoothEntity(CoordinatorEntity[GardenaBluetoothCoordinator]):
    """Coordinator entity for Gardena Bluetooth."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: GardenaBluetoothCoordinator, context: Any = None
    ) -> None:
        """Initialize coordinator entity."""
        super().__init__(coordinator, context)
        self._attr_device_info = coordinator.device_info

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self._attr_available


class GardenaBluetoothDescriptorEntity(GardenaBluetoothEntity):
    """Coordinator entity for entities with entity description."""

    def __init__(
        self,
        coordinator: GardenaBluetoothCoordinator,
        description: EntityDescription,
        context: set[str],
    ) -> None:
        """Initialize description entity."""
        super().__init__(coordinator, context)
        self._attr_unique_id = f"{coordinator.address}-{description.key}"
        self.entity_description = description
