"""Base entity for Meross Bluetooth."""

from typing import Any

from meross_ble import MODEL_FRIENDLY_NAME

from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothCoordinatorEntity,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, MANUFACTURER
from .coordinator import MerossBLEDataUpdateCoordinator


class MerossBLEEntity(
    PassiveBluetoothCoordinatorEntity[MerossBLEDataUpdateCoordinator]
):
    """Base Meross BLE entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MerossBLEDataUpdateCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._address = coordinator.ble_device.address
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_BLUETOOTH, self._address)},
            identifiers={(DOMAIN, coordinator.base_unique_id)},
            manufacturer=MANUFACTURER,
            model=MODEL_FRIENDLY_NAME.get(coordinator.model, coordinator.model.value),
            name=coordinator.device_name,
        )

    @property
    def parsed_data(self) -> dict[str, Any]:
        """Return parsed advertisement data from the device."""
        return self.coordinator.device.parsed_data
