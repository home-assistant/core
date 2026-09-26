"""Shared entity for the Axle event feed."""

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AxleCoordinator


class AxleEntity(CoordinatorEntity[AxleCoordinator]):
    """An entity belonging to one Axle event feed."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AxleCoordinator) -> None:
        """Initialize the shared service identity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name="Axle Energy",
            manufacturer="Axle Energy",
            entry_type=DeviceEntryType.SERVICE,
        )
