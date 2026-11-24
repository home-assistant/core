"""Base entity for the NEPViewer integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NepViewerCoordinator


class NepViewerEntity(CoordinatorEntity[NepViewerCoordinator]):
    """Base class for NEPViewer entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NepViewerCoordinator,
        identifier: str,
        description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._identifier = identifier
        self._attr_unique_id = f"{identifier}_{description.key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, identifier)})
