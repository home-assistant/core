"""Entity representing a Skybell HD Doorbell."""
from __future__ import annotations

from aioskybell import SkybellDevice

from homeassistant.const import ATTR_CONNECTIONS
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import SkybellDataUpdateCoordinator


class SkybellEntity(CoordinatorEntity[SkybellDataUpdateCoordinator]):
    """An HA implementation for Skybell entity."""

    _attr_attribution = "Data provided by Skybell.com"

    def __init__(
        self, coordinator: SkybellDataUpdateCoordinator, description: EntityDescription
    ) -> None:
        """Initialize a SkyBell entity."""
        super().__init__(coordinator)
        self.entity_description = description
        if description.name != coordinator.device.name:
            self._attr_name = f"{self._device.name} {description.name}"
        self._attr_unique_id = f"{self._device.device_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device.device_id)},
            manufacturer=DEFAULT_NAME,
            model=self._device.type,
            name=self._device.name,
            sw_version=self._device.firmware_ver,
        )
        if self._device.mac:
            self._attr_device_info[ATTR_CONNECTIONS] = {
                (dr.CONNECTION_NETWORK_MAC, self._device.mac)
            }

    @property
    def _device(self) -> SkybellDevice:
        """Return the device."""
        return self.coordinator.device

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
