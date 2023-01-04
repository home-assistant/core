"""Generic entity for 2N Telekomunikace integration."""
from __future__ import annotations

from py2n import Py2NDevice

from homeassistant.core import callback
from homeassistant.helpers import device_registry
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import Py2NDeviceCoordinator


class Py2NDeviceEntity(CoordinatorEntity[Py2NDeviceCoordinator]):
    """Helper class to represent a 2N Telekomunikace entity."""

    def __init__(
        self,
        coordinator: Py2NDeviceCoordinator,
        description: EntityDescription,
        device: Py2NDevice,
    ) -> None:
        """Initialize 2N Telekomunikace entity."""
        super().__init__(coordinator)
        self.device = device

        self._attr_device_info = DeviceInfo(
            configuration_url=f"https://{device.data.host}/",
            connections={(device_registry.CONNECTION_NETWORK_MAC, device.data.mac)},
            manufacturer="2N Telekomunikace",
            model=device.data.model,
            name=device.data.name,
            sw_version=device.data.firmware,
            hw_version=device.data.hardware,
        )

        self._attr_unique_id = f"{device.data.mac}_{description.name}"
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Available."""
        return self.coordinator.last_update_success

    async def async_added_to_hass(self) -> None:
        """When entity is added to HASS."""
        self.async_on_remove(self.coordinator.async_add_listener(self._update_callback))

    @callback
    def _update_callback(self) -> None:
        """Handle device update."""
        self.async_write_ha_state()
