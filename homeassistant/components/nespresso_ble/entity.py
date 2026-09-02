"""Base entity for the Nespresso integration."""

from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import NespressoBLECoordinator

_FAMILY_MODEL = {
    "vmini": "Vertuo Mini",
    "vertuo_next": "Vertuo",
    "barista": "Barista",
}


class NespressoBLEEntity(CoordinatorEntity[NespressoBLECoordinator]):
    """Base entity for a Nespresso machine."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: NespressoBLECoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        device = coordinator.data
        connections = {(CONNECTION_BLUETOOTH, device.address)}
        if device.wifi_mac:
            connections.add((CONNECTION_NETWORK_MAC, device.wifi_mac))
        self._attr_device_info = DeviceInfo(
            connections=connections,
            manufacturer="Nespresso",
            model=_FAMILY_MODEL.get(device.family),
            name=device.friendly_name(),
            serial_number=device.serial,
            sw_version=device.firmware_version,
            hw_version=device.hardware_version,
        )
