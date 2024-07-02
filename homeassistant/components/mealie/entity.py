"""Base class for Mealie entities."""

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MealieCoordinator


class MealieEntity(CoordinatorEntity[MealieCoordinator]):
    """Defines a base Mealie entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MealieCoordinator) -> None:
        """Initialize Mealie entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            entry_type=DeviceEntryType.SERVICE,
        )
