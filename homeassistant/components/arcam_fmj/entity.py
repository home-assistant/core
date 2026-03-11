"""Base entity for Arcam FMJ integration."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import ArcamFmjCoordinator


class ArcamFmjEntity(CoordinatorEntity[ArcamFmjCoordinator]):
    """Base entity for Arcam FMJ."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ArcamFmjCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
