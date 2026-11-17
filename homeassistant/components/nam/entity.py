"""Define the Nettigo Air Monitor entity."""

from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import NAMDataUpdateCoordinator


class NAMEntity(CoordinatorEntity[NAMDataUpdateCoordinator]):
    """Define a Nettigo Air Monitor entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NAMDataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.unique_id}-{description.key}"
        self.entity_description = description
