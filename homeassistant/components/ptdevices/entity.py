"""PTDevices integration."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
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
        self.coordinator = coordinator

        self._attr_unique_id = f"{device_id}_{sensor_key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            configuration_url=f"https://www.ptdevices.com/device/level/{self._device_id}",
            manufacturer="ParemTech inc.",
            model=self.coordinator.data[self._device_id].get(
                "device_type",
                None,
            ),
            sw_version=self.coordinator.data[self._device_id].get(
                "version",
                None,
            ),
            name=self.coordinator.data[self._device_id].get(
                "title",
                None,
            ),
        )

    @property
    def device(self) -> dict[str, Any]:
        """Return the device data."""
        return (dict[str, Any])(self.coordinator.data.get(self._device_id, {}))

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._sensor_key in self.coordinator.data.get(
            self._device_id, {}
        )
