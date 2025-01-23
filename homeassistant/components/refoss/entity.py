"""Entity object for shared properties of Refoss entities."""

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .bridge import RefossDataUpdateCoordinator
from .const import DOMAIN


class RefossEntity(CoordinatorEntity[RefossDataUpdateCoordinator]):
    """Refoss entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: RefossDataUpdateCoordinator, channel: int) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

        mac = coordinator.device.mac
        self.channel_id = channel
        self._attr_unique_id = f"{mac}_{channel}"
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, mac)},
            identifiers={(DOMAIN, mac)},
            manufacturer="Refoss",
            sw_version=coordinator.device.fmware_version,
            hw_version=coordinator.device.hdware_version,
            name=coordinator.device.dev_name,
        )
