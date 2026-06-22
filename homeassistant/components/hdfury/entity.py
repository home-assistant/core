"""Base class for HDFury entities."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HDFuryDataUpdateCoordinator


class HDFuryEntity(CoordinatorEntity[HDFuryDataUpdateCoordinator]):
    """Common elements for all entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HDFuryDataUpdateCoordinator,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize the entity."""

        super().__init__(coordinator)

        self.entity_description = entity_description

        serial = coordinator.config_entry.unique_id
        self._attr_unique_id = f"{serial}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
        )
