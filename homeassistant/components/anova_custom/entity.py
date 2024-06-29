"""Base entity for the Anova integration."""

from __future__ import annotations

from homeassistant.helpers.entity import Entity
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
