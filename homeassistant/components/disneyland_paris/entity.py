"""Base class for Disneyland Paris entities."""

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DisneylandParisCoordinator


class DisneylandEntity(CoordinatorEntity[DisneylandParisCoordinator]):
    """Common elements for Disneyland entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DisneylandParisCoordinator,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize the entity."""

        super().__init__(coordinator)

        self.entity_description = entity_description

        self._attr_unique_id = f"disneyland_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, "disneyland")},
            name="Disneyland",
            manufacturer="Disneyland Paris",
        )


class DisneyAdventureWorldEntity(CoordinatorEntity[DisneylandParisCoordinator]):
    """Common elements for Disney Adventure World entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DisneylandParisCoordinator,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize the entity."""

        super().__init__(coordinator)

        self.entity_description = entity_description

        self._attr_unique_id = f"disney_adventure_world_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, "disney_adventure_world")},
            name="Disney Adventure World",
            manufacturer="Disneyland Paris",
        )
