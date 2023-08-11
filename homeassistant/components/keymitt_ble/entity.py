"""MicroBot class."""
from __future__ import annotations

from typing import Any

from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothCoordinatorEntity,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from .const import MANUFACTURER
from .coordinator import MicroBotDataUpdateCoordinator


class MicroBotEntity(PassiveBluetoothCoordinatorEntity[MicroBotDataUpdateCoordinator]):
    """Generic entity for all MicroBots."""

    def __init__(self, coordinator, config_entry):
        """Initialise the entity."""
        super().__init__(coordinator)
        self._address = self.coordinator.ble_device.address
        self._attr_name = "Push"
        self._attr_unique_id = self._address
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_BLUETOOTH, self._address)},
            manufacturer=MANUFACTURER,
            model="Push",
            name="MicroBot",
        )

    @property
    def data(self) -> dict[str, Any]:
        """Return coordinator data for this entity."""
        return self.coordinator.data
