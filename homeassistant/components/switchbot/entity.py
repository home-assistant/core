"""An abstract class common to all Switchbot entities."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothCoordinatorEntity,
)
from homeassistant.const import ATTR_CONNECTIONS
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo

from .const import MANUFACTURER
from .coordinator import SwitchbotDataUpdateCoordinator


class SwitchbotEntity(PassiveBluetoothCoordinatorEntity):
    """Generic entity encapsulating common features of Switchbot device."""

    coordinator: SwitchbotDataUpdateCoordinator

    def __init__(
        self,
        coordinator: SwitchbotDataUpdateCoordinator,
        unique_id: str,
        address: str,
        name: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._last_run_success: bool | None = None
        self._unique_id = unique_id
        self._address = address
        self._attr_name = name
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_BLUETOOTH, self._address)},
            manufacturer=MANUFACTURER,
            model=self.data["modelName"],
            name=name,
        )
        if ":" not in self._address:
            # MacOS Bluetooth addresses are not mac addresses
            return
        # If the bluetooth address is also a mac address,
        # add this connection as well to prevent a new device
        # entry from being created when upgrading from a previous
        # version of the integration.
        self._attr_device_info[ATTR_CONNECTIONS].add(
            (dr.CONNECTION_NETWORK_MAC, self._address)
        )

    @property
    def data(self) -> dict[str, Any]:
        """Return coordinator data for this entity."""
        return self.coordinator.data

    @property
    def extra_state_attributes(self) -> Mapping[Any, Any]:
        """Return the state attributes."""
        return {"last_run_success": self._last_run_success}
