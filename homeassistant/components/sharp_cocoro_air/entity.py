"""Base entity for Sharp COCORO Air."""

from __future__ import annotations

from aiosharp_cocoro_air import Device, DeviceProperties

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SharpCocoroAirCoordinator


class SharpCocoroAirEntity(CoordinatorEntity[SharpCocoroAirCoordinator]):
    """Base entity for Sharp COCORO Air devices."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SharpCocoroAirCoordinator, device_id: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._device_id = device_id

    @property
    def device_data(self) -> Device | None:
        """Return the Device dataclass from coordinator data."""
        return self.coordinator.data.get(self._device_id)

    @property
    def device_properties(self) -> DeviceProperties:
        """Return the device properties dataclass."""
        dev = self.device_data
        if dev is None:
            return DeviceProperties()
        return dev.properties

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info to group entities under one device."""
        dev = self.device_data
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=dev.name if dev else "Sharp Air Purifier",
            manufacturer="Sharp",
            model=dev.model if dev else None,
            sw_version=self.device_properties.firmware,
        )

    @property
    def available(self) -> bool:
        """Return True if the device is in coordinator data."""
        return super().available and self._device_id in self.coordinator.data
