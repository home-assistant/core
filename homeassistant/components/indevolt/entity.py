"""Base entity for Indevolt integration."""

from homeassistant.helpers.device_registry import DeviceInfo
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
        return DeviceInfo(
            identifiers={(DOMAIN, coordinator.serial_number)},
            manufacturer="INDEVOLT",
            serial_number=coordinator.serial_number,
            model=coordinator.device_model,
            sw_version=coordinator.firmware_version,
            hw_version=str(coordinator.generation),
        )
