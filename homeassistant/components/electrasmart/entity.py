"""Base entity for the Electra Smart integration."""

from electrasmart.device import ElectraAirConditioner

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ElectraSmartCoordinator


class ElectraEntity(CoordinatorEntity[ElectraSmartCoordinator]):
    """Define a base Electra AC entity."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: ElectraSmartCoordinator, device: ElectraAirConditioner
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._device = device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.mac)},
            connections={(CONNECTION_NETWORK_MAC, device.mac)},
            name=device.name,
            model=device.model or None,
            manufacturer=device.manufactor or None,
            serial_number=device.serial_number or None,
            sw_version=device.fm_version or None,
            hw_version=device.hw_version or None,
        )
