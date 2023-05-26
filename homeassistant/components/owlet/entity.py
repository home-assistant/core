"""Base class for Owlet entities."""

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import OwletCoordinator


class OwletBaseEntity(CoordinatorEntity[OwletCoordinator], Entity):
    """Base class for Owlet Sock entities."""

    def __init__(
        self,
        coordinator: OwletCoordinator,
    ) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)
        self.sock = coordinator.sock
        self._attr_device_info = coordinator.device_info
        self._attr_has_entity_name = True
