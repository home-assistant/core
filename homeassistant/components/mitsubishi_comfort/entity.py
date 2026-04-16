"""Base entity for Mitsubishi Comfort integration."""

from __future__ import annotations

from mitsubishi_comfort import IndoorUnit, KumoStation

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MitsubishiComfortCoordinator


class MitsubishiComfortEntity(CoordinatorEntity[MitsubishiComfortCoordinator]):
    """Base class for all Mitsubishi Comfort entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MitsubishiComfortCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        device = coordinator.device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.serial)},
            name=device.name,
            manufacturer="Mitsubishi",
            serial_number=device.serial,
            sw_version=device.status.firmware_version,
            hw_version=device.status.hardware_version,
        )

    @property
    def _device(self) -> IndoorUnit | KumoStation:
        """Return the underlying device from coordinator data."""
        return self.coordinator.data
