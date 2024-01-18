"""LinknLink Entities."""
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LinknLinkCoordinator


class LinknLinkEntity(CoordinatorEntity[LinknLinkCoordinator]):
    """To manage the device info."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: LinknLinkCoordinator) -> None:
        """Initialize coordinator entity."""
        super().__init__(coordinator)
        self.api = coordinator.api
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.api.mac.hex())},
            connections={(dr.CONNECTION_NETWORK_MAC, self.api.mac.hex())},
            name=self.api.name,
            manufacturer=self.api.manufacturer,
            model=self.api.model,
            sw_version=str(coordinator.fw_version),
        )
