"""Support for Minut Point."""

import logging

from pypoint import Device, PointSession

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import as_local

from .const import DOMAIN
from .coordinator import PointDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class MinutPointEntity(CoordinatorEntity[PointDataUpdateCoordinator]):
    """Base Entity used by the sensors."""

    def __init__(self, coordinator: PointDataUpdateCoordinator, device_id: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.device_id = device_id
        self._name = self.device.name
        device = self.device.device
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, device["device_mac"])},
            identifiers={(DOMAIN, device["device_id"])},
            manufacturer="Minut",
            model=f"Point v{device['hardware_version']}",
            name=device["description"],
            sw_version=device["firmware"]["installed"],
            via_device=(DOMAIN, device["home"]),
        )
        if self.device_class:
            self._attr_name = f"{self._name} {self.device_class.capitalize()}"

    async def _update_callback(self):
        """Update the value of the sensor."""

    @property
    def client(self) -> PointSession:
        """Return the client object."""
        return self.coordinator.point

    @property
    def available(self) -> bool:
        """Return true if device is not offline."""
        return super().available and self.device_id in self.client.device_ids

    @property
    def device(self) -> Device:
        """Return the representation of the device."""
        return self.client.device(self.device_id)

    @property
    def extra_state_attributes(self):
        """Return status of device."""
        attrs = self.device.device_status
        attrs["last_heard_from"] = as_local(
            self.coordinator.device_updates[self.device_id]
        ).strftime("%Y-%m-%d %H:%M:%S")
        return attrs
