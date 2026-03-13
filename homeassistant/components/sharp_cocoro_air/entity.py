"""Base entity for Sharp COCORO Air."""

from __future__ import annotations

from aiosharp_cocoro_air import Device

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
        dev = coordinator.data[device_id]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=dev.name,
            manufacturer="Sharp",
            model=dev.model,
            sw_version=dev.properties.firmware,
        )

    @property
    def device_data(self) -> Device:
        """Return the Device dataclass from coordinator data."""
        return self.coordinator.data[self._device_id]

    @property
    def available(self) -> bool:
        """Return True if the device is in coordinator data."""
        return super().available and self._device_id in self.coordinator.data
