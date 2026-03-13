"""Base class for TRMNL entities."""

from __future__ import annotations

from trmnl.models import Device

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import TRMNLCoordinator


class TRMNLEntity(CoordinatorEntity[TRMNLCoordinator]):
    """Defines a base TRMNL entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TRMNLCoordinator, device: Device) -> None:
        """Initialize TRMNL entity."""
        super().__init__(coordinator)
        self._device_mac = device.mac_address
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, device.mac_address)},
            name=device.name,
            manufacturer="TRMNL",
        )

    @property
    def _device(self) -> Device:
        """Return the device from coordinator data."""
        return self.coordinator.data[self._device_mac]

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return super().available and self._device_mac in self.coordinator.data
