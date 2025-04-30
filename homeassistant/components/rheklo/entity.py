"""Base class for RHEKLO entities."""

from __future__ import annotations

from typing import Any

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
from .coordinator import RhekloUpdateCoordinator


def _get_device_connections(mac_address: str) -> set[tuple[str, str]]:
    """Get device connections."""
    try:
        mac_address_hex = mac_address.replace(":", "")
    except ValueError:  # MacAddress may be invalid if the gateway is offline
        return set()
    return {(dr.CONNECTION_NETWORK_MAC, mac_address_hex)}


class RhekloEntity(CoordinatorEntity[RhekloUpdateCoordinator]):
    """Representation of an RHEKLO entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RhekloUpdateCoordinator,
        device_id: int,
        device_data: dict,
        description: EntityDescription,
        use_device_key: bool = False,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._device_id = device_id
        self._attr_unique_id = (
            f"{coordinator.entry_unique_id}_{device_id}_{description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{coordinator.entry_unique_id}_{device_id}")},
            name=device_data[DEVICE_DATA_DISPLAY_NAME],
            hw_version=device_data[DEVICE_DATA_PRODUCT],
            sw_version=device_data[DEVICE_DATA_FIRMWARE_VERSION],
            model=device_data[DEVICE_DATA_MODEL_NAME],
            manufacturer=KOHLER,
            connections=_get_device_connections(device_data[DEVICE_DATA_MAC_ADDRESS]),
        )
        self._use_device_key = use_device_key

    @property
    def _device_data(self) -> dict[str, Any]:
        """Return the device data."""
        return self.coordinator.data[GENERATOR_DATA_DEVICE]

    @property
    def _rheklo_value(self) -> str:
        """Return the sensor value."""
        if self._use_device_key:
            return self._device_data[self.entity_description.key]
        return self.coordinator.data[self.entity_description.key]

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self._device_data[DEVICE_DATA_IS_CONNECTED]
