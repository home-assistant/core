"""Base class for Nest entities."""

from __future__ import annotations

from typing import Any, Generic, TypeVar, cast

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import NestCoordinator
from .pynest.models import NestDevice

DeviceT = TypeVar("DeviceT", bound=NestDevice)


class NestEntity(CoordinatorEntity[NestCoordinator], Generic[DeviceT]):
    """Base class for Nest entities."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NestCoordinator,
        device: DeviceT,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._device: DeviceT = device
        self._attr_device_info = self.generate_device_info()
        self._attr_unique_id = device.serial_number

    async def _set_device_data(self, data: dict[str, Any]) -> None:
        """Set device data and update HA state."""
        await self.coordinator.async_set_device_data(self.device, data)
        self.async_write_ha_state()

    @property
    def device(self) -> DeviceT:
        """Return the device data for this entity."""
        # Return the most recent device data from the coordinator
        return cast(
            DeviceT, self.coordinator.data.get(self._device.serial_number, self._device)
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and self._device.serial_number in self.coordinator.data
            and self.device.online
        )

    def generate_device_info(self) -> DeviceInfo:
        """Generate the device info for the entity."""
        location = self._device.location
        name = self._device.name
        if location and location.lower() not in name.lower():
            device_name = f"{location} {name}".strip()
        else:
            device_name = name.strip()

        device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device.serial_number)},
            name=device_name,
            manufacturer="Google",
            model=self._device.model,
            sw_version=self._device.software_version,
            suggested_area=self._device.location,
        )

        if mac := self._device.mac_address:
            device_info["connections"] = {
                (dr.CONNECTION_NETWORK_MAC, dr.format_mac(mac))
            }

        if hw_version := self._device.hardware_version:
            device_info["hw_version"] = hw_version

        return device_info
