"""Base entity for the Nespresso Vertuo integration."""

from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import NespressoBLECoordinator


class NespressoBLEEntity(CoordinatorEntity[NespressoBLECoordinator]):
    """Base entity for a Nespresso Vertuo machine."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: NespressoBLECoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        device = coordinator.data
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, device.address)},
            manufacturer="Nespresso",
            model="Vertuo Mini",
            name=device.friendly_name(),
            serial_number=device.serial or None,
            sw_version=device.firmware_version or None,
        )
