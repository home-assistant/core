"""Base class for ezbeq entities."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EzBEQCoordinator


class EzBEQEntity(CoordinatorEntity[EzBEQCoordinator]):
    """Defines a base ezbeq entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: EzBEQCoordinator) -> None:
        """Initialize ezbeq entity."""
        super().__init__(coordinator)
        assert coordinator.config_entry
        assert coordinator.config_entry.unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.unique_id)},
            name="EzBEQ",
            manufacturer="EzBEQ",
            sw_version=coordinator.client.version,
        )
