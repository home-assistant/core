"""Base entity for Overseerr."""

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OverseerrCoordinator


class OverseerrEntity(CoordinatorEntity[OverseerrCoordinator]):
    """Defines a base Overseerr entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: OverseerrCoordinator, key: str) -> None:
        """Initialize Overseerr entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            entry_type=DeviceEntryType.SERVICE,
        )
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-{key}"
