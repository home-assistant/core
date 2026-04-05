"""Base entity for Mitsubishi Comfort integration."""

from __future__ import annotations

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
        self._device = coordinator.device

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.available

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.serial)},
            name=self._device.name,
            manufacturer="Mitsubishi",
            sw_version=self._device.status.firmware_version,
            hw_version=self._device.status.hardware_version,
        )
