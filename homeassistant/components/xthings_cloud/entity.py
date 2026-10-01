"""Base entity for Xthings Cloud."""

from typing import Any, override

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
    @override
    def available(self) -> bool:
        """Return whether device is available (online)."""
        if self._device_id not in self.coordinator.data:
            return False
        if self.coordinator.uses_native_mqtt(self._device_id):
            # Native bulbs confirm their own state; a failed account poll does
            # not make a bulb that is still answering unreachable.
            return self.device_data["online"]
        return super().available and self.device_data["online"]
