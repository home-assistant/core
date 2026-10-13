"""Base entity for the Tile BLE integration."""

from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothCoordinatorEntity,
)
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo

from .coordinator import TileBleCoordinator


class TileBleEntity(PassiveBluetoothCoordinatorEntity[TileBleCoordinator]):
    """Base class for Tile BLE entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TileBleCoordinator, name: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, coordinator.address)},
            manufacturer="Tile Inc.",
            name=name,
        )
