"""Entity object for shared properties of meross_scan entities."""

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MerossDataUpdateCoordinator


class MerossEntity(CoordinatorEntity[MerossDataUpdateCoordinator]):
    """entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MerossDataUpdateCoordinator, channel: int) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.channel = channel
        mac = coordinator.device.mac
        self._attr_unique_id = f"{mac}_{channel}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            connections={(CONNECTION_NETWORK_MAC, mac)},
            manufacturer="Meross",
            name=coordinator.device.device_type,
            model=coordinator.device.device_type,
            sw_version=coordinator.device.fmware_version,
            hw_version=coordinator.device.hdware_version,
        )
