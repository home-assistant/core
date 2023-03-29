"""Base entity for the Anova integration."""
from __future__ import annotations

from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import AnovaCoordinator


class AnovaEntity(CoordinatorEntity[AnovaCoordinator], Entity):
    """Defines a Anova entity."""

    def __init__(self, coordinator: AnovaCoordinator) -> None:
        """Initialize the Anova entity."""
        super().__init__(coordinator)
        self.device = coordinator.anova_device
        self._attr_device_info = coordinator.device_info
        self._attr_has_entity_name = True


class AnovaDescriptionEntity(AnovaEntity, Entity):
    """Defines a Anova entity that uses a description."""

    def __init__(
        self, coordinator: AnovaCoordinator, description: EntityDescription
    ) -> None:
        """Initialize the entity and declare unique id based on description key."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator._device_unique_id}_{description.key}"
