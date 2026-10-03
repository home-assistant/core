"""Shared entity behavior for DRIQON devices."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DriqonCoordinator
from .types import Device, DeviceMap


class DriqonEntity(CoordinatorEntity[DeviceMap]):
    """Base class that links a cloud entity to its physical DRIQON device."""

    _attr_has_entity_name = True
    _attr_translation_key = "on_off"

    def __init__(self, coordinator: DriqonCoordinator, device: Device) -> None:
        super().__init__(coordinator)
        self.device_id = device["device_id"]
        if device.get("device_type") == "single_node":
            self._attr_entity_picture = "/api/driqon/images/single_node.png"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.device_id)},
            manufacturer="DRIQON",
            name=device.get("device_name") or self.device_id,
            model=device.get("device_type"),
            sw_version=device.get("firmware_version"),
            serial_number=self.device_id,
        )

    @property
    def available(self) -> bool:
        """Mark missing, offline, or cloud-disconnected devices unavailable."""
        device = self.coordinator.data.get(self.device_id)
        return (
            super().available
            and device is not None
            and str(device.get("status", "")).upper() == "ONLINE"
        )
