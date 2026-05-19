"""Base entity for Indevolt integration."""

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IndevoltCoordinator


class IndevoltEntity(CoordinatorEntity[IndevoltCoordinator]):
    """Base Indevolt entity with up-to-date device info."""

    _attr_has_entity_name = True

    @property
    def serial_number(self) -> str:
        """Return the device serial number."""
        return self.coordinator.serial_number

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for registry."""
        coordinator = self.coordinator
        connections: set[tuple[str, str]] = set()
        if coordinator.mac_address:
            connections.add((CONNECTION_NETWORK_MAC, coordinator.mac_address))
        return DeviceInfo(
            identifiers={(DOMAIN, coordinator.serial_number)},
            connections=connections,
            manufacturer="INDEVOLT",
            serial_number=coordinator.serial_number,
            model=coordinator.device_model,
            sw_version=coordinator.firmware_version,
            hw_version=str(coordinator.generation),
        )
