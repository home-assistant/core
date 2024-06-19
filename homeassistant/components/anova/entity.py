"""Base entity for the Anova integration."""

from __future__ import annotations

from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import AnovaCoordinator


class AnovaEntity(CoordinatorEntity[AnovaCoordinator], Entity):
    """Defines an Anova entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AnovaCoordinator) -> None:
        """Initialize the Anova entity."""
        super().__init__(coordinator)
        self.device = coordinator.anova_device
        self._attr_device_info = coordinator.device_info

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.data is not None and super().available


class AnovaDescriptionEntity(AnovaEntity):
    """Defines an Anova entity that uses a description."""

    def __init__(
        self, coordinator: AnovaCoordinator, description: EntityDescription
    ) -> None:
        """Initialize the entity and declare unique id based on description key."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_unique_id}_{description.key}"
