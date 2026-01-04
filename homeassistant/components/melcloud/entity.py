"""Base entity for MELCloud integration."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import MelCloudDeviceUpdateCoordinator


class MelCloudEntity(CoordinatorEntity[MelCloudDeviceUpdateCoordinator]):
    """Base class for MELCloud entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MelCloudDeviceUpdateCoordinator,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.coordinator.device_available
