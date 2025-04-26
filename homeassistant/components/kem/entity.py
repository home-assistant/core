"""Base class for KEM entities."""

from __future__ import annotations

from homeassistant.const import ATTR_CONNECTIONS
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DEVICE_DATA_DISPLAY_NAME,
    DEVICE_DATA_FIRMWARE_VERSION,
    DEVICE_DATA_IS_CONNECTED,
    DEVICE_DATA_MAC_ADDRESS,
    DEVICE_DATA_MODEL_NAME,
    DEVICE_DATA_PRODUCT,
    DOMAIN,
    GENERATOR_DATA_DEVICE,
    KOHLER,
)
from .coordinator import KemUpdateCoordinator


def _get_device_connections(mac_address: str) -> set[tuple[str, str]]:
    """Get device connections."""
    try:
        mac_address_hex = mac_address.replace(":", "")
    except ValueError:  # MacAddress may be invalid if the gateway is offline
        return set()
    return {(dr.CONNECTION_NETWORK_MAC, mac_address_hex)}


class KemEntity(CoordinatorEntity[KemUpdateCoordinator]):
    """Representation of an KEM entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: KemUpdateCoordinator,
        device_id: int,
        device_data: dict,
        description: EntityDescription,
        use_device_key: bool = False,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(self._device_id))},
            name=device_data[DEVICE_DATA_DISPLAY_NAME],
            hw_version=device_data[DEVICE_DATA_PRODUCT],
            sw_version=device_data[DEVICE_DATA_FIRMWARE_VERSION],
            model=device_data[DEVICE_DATA_MODEL_NAME],
            manufacturer=KOHLER,
        )
        self._use_device_key = use_device_key
        self._attr_device_info[ATTR_CONNECTIONS] = _get_device_connections(
            device_data[DEVICE_DATA_MAC_ADDRESS]
        )

    @property
    def _device_data(self) -> dict:
        """Return the device data."""
        return self.coordinator.data[GENERATOR_DATA_DEVICE]

    @property
    def _kem_value(self) -> str:
        """Return the sensor value."""
        if self._use_device_key:
            return self._device_data[self.entity_description.key]
        return self.coordinator.data[self.entity_description.key]

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self._device_data[DEVICE_DATA_IS_CONNECTED]
