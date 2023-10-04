"""Entity class for Renson ventilation unit."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RensonCoordinator


class RensonEntity(CoordinatorEntity[RensonCoordinator]):
    """Renson entity."""

    def __init__(self, name: str, coordinator: RensonCoordinator) -> None:
        """Initialize the Renson entity."""
        super().__init__(coordinator)

        self._attr_device_info = DeviceInfo(
            name="Healthbox3",
            identifiers={(DOMAIN, coordinator.api.serial)},
            manufacturer="Renson",
            model=coordinator.api.description,
            hw_version=coordinator.api.warranty_number,
            sw_version=coordinator.api.firmware_version,
        )
        self._attr_unique_id = coordinator.api.serial + name
        self.api = coordinator.api
