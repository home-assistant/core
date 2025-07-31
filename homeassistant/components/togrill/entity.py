"""Provides the base entities."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import ToGrillCoordinator


class ToGrillEntity(CoordinatorEntity[ToGrillCoordinator]):
    """Coordinator entity for Gardena Bluetooth."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ToGrillCoordinator, context: Any = None) -> None:
        """Initialize coordinator entity."""
        super().__init__(coordinator, context)
        self._attr_device_info = coordinator.device_info

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self._attr_available
