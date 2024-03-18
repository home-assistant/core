"""Arve base entity."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import ArveCoordinator


class ArveDeviceEntity(CoordinatorEntity[ArveCoordinator]):
    """Defines a base Arve device entity."""

    _attr_has_entity_name = True
    _attr_available = True

    def __init__(self, coordinator: ArveCoordinator) -> None:
        """Initialize the Arve device entity."""
        super().__init__(coordinator)

        self._entry = coordinator.config_entry
        self.arve = coordinator.arve
        self.coordinator = coordinator
