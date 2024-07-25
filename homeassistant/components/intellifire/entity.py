"""Platform for shared base classes for sensors."""

from __future__ import annotations

from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import IntelliFireDataUpdateCoordinator


class IntellifireEntity(CoordinatorEntity[IntelliFireDataUpdateCoordinator]):
    """Define a generic class for IntelliFire entities."""

    _attr_attribution = "Data provided by unpublished Intellifire API"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IntelliFireDataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Class initializer."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self.identifiers = ({("IntelliFire", f"{coordinator.fireplace.serial}]")},)
        self._attr_unique_id = f"{description.key}_{coordinator.fireplace.serial}"

        # Configure the Device Info
        self._attr_device_info = self.coordinator.device_info
