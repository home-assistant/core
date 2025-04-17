"""Support for Oncue sensors."""

from __future__ import annotations

from homeassistant.const import ATTR_CONNECTIONS
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import KemUpdateCoordinator


class KemEntity(CoordinatorEntity[KemUpdateCoordinator], Entity):
    """Representation of an Oncue entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: KemUpdateCoordinator,
        device_id: int,
        device_data: dict,
        description: EntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entity_description = description
        self._device_id = device_id
        self._attr_unique_id = f"{self._device_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(self._device_id))},
            name=device_data["device"]["displayName"],
            hw_version=device_data["device"]["product"],
            sw_version=device_data["device"]["firmwareVersion"],
            model=device_data["device"]["modelDisplayName"],
            manufacturer="Kohler",
        )
        splits = self.entity_description.key.split(":")
        if len(splits) > 1:
            self.use_device_key = True
            self.key = splits[1]
        else:
            self.use_device_key = False
            self.key = self.entity_description.key

        self._attr_name = self.key

        try:
            mac_address_hex = hex(int(device_data["device"]["macAddress"]))[2:]
        except ValueError:  # MacAddress may be invalid if the gateway is offline
            return
        self._attr_device_info[ATTR_CONNECTIONS] = {
            (dr.CONNECTION_NETWORK_MAC, mac_address_hex)
        }

    @property
    def _oncue_value(self) -> str:
        """Return the sensor value."""
        device = self.coordinator.data[self._device_id]
        if self.use_device_key:
            value = device["device"][self.key]
        else:
            value = device[self.key]
        return value

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # # The binary sensor that tracks the connection should not go unavailable.
        # if self.entity_description.key != CONNECTION_ESTABLISHED_KEY:
        #     # If Kohler returns -- the entity is unavailable.
        #     if self._oncue_value == VALUE_UNAVAILABLE:
        #         return False
        #     # If the cloud is reporting that the generator is not connected
        #     # this also indicates the data is not available.
        #     # The battery voltage sensor reports 0.0 rather than
        #     # -- hence the purpose of this check.
        #     device: OncueDevice = self.coordinator.data[self._device_id]
        #     conn_established: OncueSensor = device.sensors[CONNECTION_ESTABLISHED_KEY]
        #     if (
        #         conn_established is not None
        #         and conn_established.value == VALUE_UNAVAILABLE
        #     ):
        #         return False
        return super().available
