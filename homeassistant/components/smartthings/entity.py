"""Support for SmartThings Cloud."""

from __future__ import annotations

from typing import Any

from pysmartthings.models import Attribute, Capability

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SmartThingsDeviceCoordinator
from .const import DOMAIN


class SmartThingsEntity(CoordinatorEntity[SmartThingsDeviceCoordinator]):
    """Defines a SmartThings entity."""

    def __init__(self, coordinator: SmartThingsDeviceCoordinator) -> None:
        """Initialize the instance."""
        super().__init__(coordinator)
        self._attr_name = coordinator.device.label
        self._attr_unique_id = coordinator.device.device_id
        self._attr_device_info = DeviceInfo(
            configuration_url="https://account.smartthings.com",
            identifiers={(DOMAIN, coordinator.device.device_id)},
            name=coordinator.device.label,
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""
        await super().async_added_to_hass()
        self._update_attr()

    def supports_capability(self, capability: Capability) -> bool:
        """Test if device supports a capability."""
        return capability in self.coordinator.data

    def get_attribute_value(self, capability: Capability, attribute: Attribute) -> Any:
        """Get the value of a device attribute."""
        return self.coordinator.data[capability][attribute].value

    def _update_attr(self) -> None:
        """Update the attributes."""

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attr()
        super()._handle_coordinator_update()
