"""Provides the base entities."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import ToGrillCoordinator


class ToGrillEntity(CoordinatorEntity[ToGrillCoordinator]):
    """Coordinator entity for Gardena Bluetooth."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ToGrillCoordinator) -> None:
        """Initialize coordinator entity."""
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
