"""An abstract class common to all Switchbot entities."""
from __future__ import annotations

from abc import abstractmethod
from collections.abc import Mapping
from typing import Any

from switchbot import SwitchbotDevice

from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothCoordinatorEntity,
)
from homeassistant.const import ATTR_CONNECTIONS
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo

from .const import MANUFACTURER
from .coordinator import SwitchbotDataUpdateCoordinator


class SwitchbotEntity(PassiveBluetoothCoordinatorEntity):
    """Generic entity encapsulating common features of Switchbot device."""

    coordinator: SwitchbotDataUpdateCoordinator
    _device: SwitchbotDevice
    _attr_has_entity_name = True

    def __init__(self, coordinator: SwitchbotDataUpdateCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._device = coordinator.device
        self._last_run_success: bool | None = None
        self._address = coordinator.ble_device.address
        self._attr_unique_id = coordinator.base_unique_id
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_BLUETOOTH, self._address)},
            manufacturer=MANUFACTURER,
            model=coordinator.model,  # Sometimes the modelName is missing from the advertisement data
            name=coordinator.device_name,
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


class SwitchbotSubscribeEntity(SwitchbotEntity):
    """Base class for Switchbot entities that use subscribe."""

    @abstractmethod
    def _async_update_attrs(self) -> None:
        """Update the entity attributes."""

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data update."""
        self._async_update_attrs()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(self._device.subscribe(self._handle_coordinator_update))
        return await super().async_added_to_hass()

    async def async_update(self) -> None:
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self._device.update()
