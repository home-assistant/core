"""Base entity for Xthings Cloud."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import XthingsCloudCoordinator


class XthingsCloudEntity(CoordinatorEntity[XthingsCloudCoordinator]):
    """Xthings Cloud base entity."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        coordinator: XthingsCloudCoordinator,
        device_id: str,
        device_data: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = device_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device_data.get("name", "Xthings Device"),
            manufacturer="Xthings",
            model=device_data.get("model", "Unknown"),
            sw_version=device_data.get("version"),
        )

    @property
    def device_data(self) -> dict[str, Any]:
        """Return current device data."""
        if self.coordinator.data and self._device_id in self.coordinator.data:
            return self.coordinator.data[self._device_id]
        return {}

    @property
    def available(self) -> bool:
        """Return whether device is available (online)."""
        return self.coordinator.last_update_success and self.device_data.get(
            "online", False
        )
