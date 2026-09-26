"""Base entity for the Vitesy integration."""

from typing import override

from aiovitesy.api import VitesyDevice

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import VitesyDataUpdateCoordinator


class VitesyEntity(CoordinatorEntity[VitesyDataUpdateCoordinator]):
    """Base class for all Vitesy entities."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: VitesyDataUpdateCoordinator, device_id: str
    ) -> None:
        """Initialize the entity for a single Vitesy device."""
        super().__init__(coordinator)
        self._device_id = device_id

        device = self.device
        # The Vitesy Hub device id is the device's MAC address.
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            connections={(CONNECTION_NETWORK_MAC, device_id)},
            manufacturer="Vitesy",
            model=device.device_type or None,
            model_id=device.model or None,
            name=device.name,
            sw_version=device.firmware_version or None,
        )

    @property
    def device(self) -> VitesyDevice:
        """Return this entity's device from the latest coordinator data."""
        return self.coordinator.data[self._device_id]

    @property
    @override
    def available(self) -> bool:
        """Return True when the device is present and reporting as connected."""
        return (
            super().available
            and self._device_id in self.coordinator.data
            and self.device.connected
        )
