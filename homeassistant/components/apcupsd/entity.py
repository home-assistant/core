"""Base entity for APCUPSd integration."""

from __future__ import annotations

from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import APCUPSdCoordinator


class APCUPSdEntity(CoordinatorEntity[APCUPSdCoordinator]):
    """Base entity for APCUPSd integration."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: APCUPSdCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize the APCUPSd entity."""
        super().__init__(coordinator, context=description.key.upper())

        self.entity_description = description
        self._attr_unique_id = f"{coordinator.unique_device_id}_{description.key}"
        self._attr_device_info = coordinator.device_info
