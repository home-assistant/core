"""Base class for all SMLIGHT entities."""

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import SmBaseDataUpdateCoordinator, device_info


class SmEntity(CoordinatorEntity[SmBaseDataUpdateCoordinator]):
    """Base class for all SMLight entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SmBaseDataUpdateCoordinator) -> None:
        """Initialize entity with device."""
        super().__init__(coordinator)
        self._attr_device_info = device_info(
            coordinator.data.info, coordinator.client.host
        )
