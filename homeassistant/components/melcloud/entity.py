"""Base entity for MELCloud integration."""

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import MelCloudDeviceUpdateCoordinator


class MelCloudEntity(CoordinatorEntity[MelCloudDeviceUpdateCoordinator]):
    """Base class for MELCloud entities."""

    _attr_has_entity_name = True

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.coordinator.device_available
