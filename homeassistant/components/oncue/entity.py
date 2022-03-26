"""Support for Oncue sensors."""
from __future__ import annotations

from aiooncue import OncueDevice, OncueSensor

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo, Entity, EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN


class OncueEntity(CoordinatorEntity, Entity):
    """Representation of an Oncue entity."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_id: str,
        device: OncueDevice,
        sensor: OncueSensor,
        description: EntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_{description.key}"
        self._attr_name = f"{device.name} {sensor.display_name}"
        mac_address_hex = hex(int(device.sensors["MacAddress"].value))[2:]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            connections={(dr.CONNECTION_NETWORK_MAC, mac_address_hex)},
            name=device.name,
            hw_version=device.hardware_version,
            sw_version=device.sensors["FirmwareVersion"].display_value,
            model=device.sensors["GensetModelNumberSelect"].display_value,
            manufacturer="Kohler",
        )

    @property
    def _oncue_value(self) -> str:
        """Return the sensor value."""
        device: OncueDevice = self.coordinator.data[self._device_id]
        sensor: OncueSensor = device.sensors[self.entity_description.key]
        return sensor.value
