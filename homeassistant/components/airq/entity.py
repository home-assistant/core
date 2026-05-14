"""Base entity for the air-Q integration."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import AirQCoordinator


class AirQEntity(CoordinatorEntity[AirQCoordinator]):
    """Base class for air-Q entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AirQCoordinator, key: str) -> None:
        """Initialize an air-Q entity."""
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.device_id}_{key}"
