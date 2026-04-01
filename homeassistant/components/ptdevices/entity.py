"""PTDevices integration."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PTDevicesCoordinator


class PTDevicesEntity(CoordinatorEntity[PTDevicesCoordinator]):
    """Defines a base PTDevices entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PTDevicesCoordinator,
        sensor_key: str,
        device_id: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator=coordinator)
        self._sensor_key = sensor_key
        self._device_id = device_id
        self._user_id = coordinator.data[self._device_id]["user_id"]

        self._attr_unique_id = f"{self._user_id}_{device_id}_{sensor_key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{self._user_id}_{self._device_id}")},
            connections={(CONNECTION_NETWORK_MAC, self._device_id)},
            configuration_url=f"https://www.ptdevices.com/device/level/{self.device['id']}",
            manufacturer="ParemTech inc.",
            model=self.device["device_type"],
            sw_version=self.device["version"],
            name=self.device["title"],
        )

    @property
    def device(self) -> dict[str, Any]:
        """Return the device data."""
        return self.coordinator.data[self._device_id]
