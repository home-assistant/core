"""Dormakaba dKey integration base entity."""
from __future__ import annotations

import abc

from py_dormakaba_dkey import DKEYLock
from py_dormakaba_dkey.commands import Notifications

from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)


class DormakabaDkeyEntity(CoordinatorEntity[DataUpdateCoordinator[None]]):
    """Dormakaba dKey base entity."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: DataUpdateCoordinator[None], lock: DKEYLock
    ) -> None:
        """Initialize a Dormakaba dKey entity."""
        super().__init__(coordinator)
        self._lock = lock
        self._attr_device_info = DeviceInfo(
            name=lock.device_info.device_name or lock.device_info.device_id,
            model="MTL 9291",
            sw_version=lock.device_info.sw_version,
            connections={(dr.CONNECTION_BLUETOOTH, lock.address)},
        )
        self._async_update_attrs()

    @abc.abstractmethod
    @callback
    def _async_update_attrs(self) -> None:
        """Handle updating _attr values."""

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data update."""
        self._async_update_attrs()
        self.async_write_ha_state()

    @callback
    def _handle_state_update(self, update: Notifications) -> None:
        """Handle data update."""
        self.coordinator.async_set_updated_data(None)

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(self._lock.register_callback(self._handle_state_update))
        return await super().async_added_to_hass()
