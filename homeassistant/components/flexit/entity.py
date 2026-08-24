"""Base entity for the Flexit integration."""

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import FlexitDataCoordinator


class FlexitEntity(CoordinatorEntity[FlexitDataCoordinator]):
    """Base class for Flexit entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: FlexitDataCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
