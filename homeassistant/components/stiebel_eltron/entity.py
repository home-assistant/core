"""Base entity for the STIEBEL ELTRON integration."""

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import StiebelEltronDataCoordinator


class StiebelEltronEntity(CoordinatorEntity[StiebelEltronDataCoordinator]):
    """Base class for STIEBEL ELTRON entities."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: StiebelEltronDataCoordinator, unique_id: str
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = unique_id
