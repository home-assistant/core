"""Base entity for Watts Vision integration."""

from __future__ import annotations

from typing import cast

from visionpluspython.models import Device

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WattsVisionDeviceCoordinator


class WattsVisionEntity[_T: Device](CoordinatorEntity[WattsVisionDeviceCoordinator]):
    """Base entity for Watts Vision devices."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: WattsVisionDeviceCoordinator, device_id: str
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, context=device_id)
        self.device_id = device_id
        self._attr_unique_id = device_id
        device = coordinator.data.device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.device_id)},
            name=device.device_name,
            manufacturer="Watts",
            model=f"Vision+ {device.device_type}",
            suggested_area=device.room_name,
        )

    @property
    def device(self) -> _T:
        """Return the device from the coordinator data."""
        return cast(_T, self.coordinator.data.device)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.coordinator.data.device.is_online
