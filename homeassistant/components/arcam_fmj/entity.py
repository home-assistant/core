"""Base entity for Arcam FMJ integration."""

from __future__ import annotations

from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import ArcamFmjCoordinator


class ArcamFmjEntity(CoordinatorEntity[ArcamFmjCoordinator]):
    """Base entity for Arcam FMJ."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ArcamFmjCoordinator,
        description: EntityDescription | None = None,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
        self._attr_entity_registry_enabled_default = coordinator.state.zn == 1
        self._attr_unique_id = coordinator.zone_unique_id
        if description is not None:
            self._attr_unique_id = f"{self._attr_unique_id}-{description.key}"
            self.entity_description = description
