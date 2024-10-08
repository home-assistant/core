"""Base entity for Daikin."""

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import DaikinCoordinator


class DaikinEntity(CoordinatorEntity[DaikinCoordinator]):
    """Base entity for Daikin."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: DaikinCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.device = coordinator.device
        info = self.device.values
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, self.device.mac)},
            manufacturer="Daikin",
            model=info.get("model"),
            name=info.get("name"),
            sw_version=info.get("ver", "").replace("_", "."),
        )
