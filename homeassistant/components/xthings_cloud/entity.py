"""Base entity for Xthings Cloud."""

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
        """Initialize the entity."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = device_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device_data["name"],
            manufacturer="Xthings",
            model=device_data["model"],
            sw_version=device_data.get("version"),
        )

    @property
    def device_data(self) -> dict[str, Any]:
        """Return current device data."""
        return self.coordinator.data[self._device_id]

    @property
    def available(self) -> bool:
        """Return whether device is available (online)."""
        return (
            super().available
            and self._device_id in self.coordinator.data
            and self.device_data["online"]
        )
