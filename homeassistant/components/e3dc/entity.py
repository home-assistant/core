"""Base entity for E3/DC devices."""

from typing import TYPE_CHECKING

from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import E3dcDataUpdateCoordinator


class E3dcEntity(CoordinatorEntity[E3dcDataUpdateCoordinator]):
    """Defines a base E3/DC entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: E3dcDataUpdateCoordinator,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        serial = coordinator.config_entry.unique_id
        if TYPE_CHECKING:
            assert serial is not None
        self._attr_unique_id = f"{serial}_{entity_description.key}"
        self._attr_device_info = coordinator.device_info
