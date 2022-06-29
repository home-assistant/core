"""Platform for shared base classes for sensors."""
from __future__ import annotations

from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import IntellifireDataUpdateCoordinator


class IntellifireEntity(CoordinatorEntity[IntellifireDataUpdateCoordinator]):
    """Define a generic class for Intellifire entities."""

    _attr_attribution = "Data provided by unpublished Intellifire API"

    def __init__(
        self,
        coordinator: IntellifireDataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Class initializer."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        # Set the Display name the User will see
        self._attr_name = f"Fireplace {description.name}"
        self._attr_unique_id = f"{description.key}_{coordinator.read_api.data.serial}"
        # Configure the Device Info
        self._attr_device_info = self.coordinator.device_info
