"""Base entities for the Fluss+ integration."""

import logging

from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import FlussDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class FlussEntity(CoordinatorEntity[FlussDataUpdateCoordinator]):
    """Base class for Fluss entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FlussDataUpdateCoordinator,
        device_id: str,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.device_id = device_id
        self.entity_description = entity_description
        self._attr_unique_id = f"{device_id}_{entity_description.key}"

    @property
    def device(self) -> dict | None:
        """Return the device data from the coordinator."""
        return self.coordinator.data.get(self.device_id)
