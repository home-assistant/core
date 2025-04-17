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
            name=device_data["displayName"],
            hw_version=device_data["product"],
            sw_version=device_data["firmwareVersion"],
            model=device_data["modelDisplayName"],
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
            mac_address_hex = device_data["macAddress"].replace(":", "")
        except ValueError:  # MacAddress may be invalid if the gateway is offline
            return
        self._attr_device_info[ATTR_CONNECTIONS] = {
            (dr.CONNECTION_NETWORK_MAC, mac_address_hex)
        }

    @property
    def _kem_value(self) -> str:
        """Return the sensor value."""
        generator_data = self.coordinator.data
        if self.use_device_key:
            value = generator_data["device"][self.key]
        else:
            value = generator_data[self.key]
        return value

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.available:
            return False
        if not self.coordinator.data["device"]["isConnected"]:
            return False
        return super().available
