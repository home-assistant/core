"""Base class for Transmission entities."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TransmissionDataUpdateCoordinator


class TransmissionEntity(CoordinatorEntity[TransmissionDataUpdateCoordinator]):
    """Defines a base Transmission entity."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: TransmissionDataUpdateCoordinator, key: str
    ) -> None:
        """Initialize Transmission entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            manufacturer="Transmission",
        )
