"""Base class for Papouch entities."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import PapouchDataUpdateCoordinator


class PapouchEntity(CoordinatorEntity[PapouchDataUpdateCoordinator]):
    """Common class for all Papouch entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PapouchDataUpdateCoordinator, entry) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)

        self._attr_device_info = DeviceInfo(
            identifiers={(entry.domain, entry.entry_id)},
            name=coordinator.device.name,
            manufacturer=coordinator.device.manufacturer,
        )
