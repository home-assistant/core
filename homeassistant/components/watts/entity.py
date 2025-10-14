"""Base entity for Watts Vision integration."""

from __future__ import annotations

from visionpluspython.models import Device

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WattsVisionDeviceCoordinator


class WattsVisionEntity(CoordinatorEntity[WattsVisionDeviceCoordinator]):
    """Base entity for Watts Vision integration."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: WattsVisionDeviceCoordinator, device_id: str
    ) -> None:
        """Initialize the entity."""

        super().__init__(coordinator, context=device_id)
        self.device_id = device_id
        self._attr_unique_id = device_id

        if self.device:
            device_name = self.device.device_name
            if hasattr(self.device, "room_name") and self.device.room_name:
                device_name = f"{self.device.room_name} {device_name}"

            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, self.device_id)},
                name=device_name,
                manufacturer="Watts",
                model=f"Vision+ {self.device.device_type}",
            )

    @property
    def device(self) -> Device:
        """Return the device object from the coordinator data."""
        if self.coordinator.data is None:
            raise RuntimeError("Empty device coordinator data")
        return self.coordinator.data

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and self.coordinator.data is not None
            and self.coordinator.data.is_online
        )
