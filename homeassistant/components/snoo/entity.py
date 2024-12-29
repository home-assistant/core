"""Base entity for the Snoo integration."""

from __future__ import annotations

from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import SnooCoordinator


class SnooDescriptionEntity(CoordinatorEntity[SnooCoordinator]):
    """Defines an Snoo entity that uses a description."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: SnooCoordinator, description: EntityDescription
    ) -> None:
        """Initialize the Snoo entity."""
        super().__init__(coordinator)
        self.device = coordinator.device
        self._attr_device_info = coordinator.device_info
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_unique_id}_{description.key}"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.data is not None and super().available
