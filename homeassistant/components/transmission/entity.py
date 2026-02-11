"""Base class for Transmission entities."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TransmissionDataUpdateCoordinator


class TransmissionEntity(CoordinatorEntity[TransmissionDataUpdateCoordinator]):
    """Defines a base Transmission entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TransmissionDataUpdateCoordinator,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize Transmission entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}-{entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
        )
