"""Base entity for the Fresh-r integration."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import FreshrReadingsCoordinator


class FreshrEntity(CoordinatorEntity[FreshrReadingsCoordinator]):
    """Base class for Fresh-r entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: FreshrReadingsCoordinator) -> None:
        """Initialize the Fresh-r entity."""
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
