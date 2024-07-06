"""Base class for Mealie entities."""

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MealieCoordinator


class MealieEntity(CoordinatorEntity[MealieCoordinator]):
    """Defines a base Mealie entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MealieCoordinator, key: str) -> None:
        """Initialize Mealie entity."""
        super().__init__(coordinator)
        unique_id = coordinator.config_entry.unique_id
        assert unique_id is not None
        self._attr_unique_id = f"{unique_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            entry_type=DeviceEntryType.SERVICE,
        )
