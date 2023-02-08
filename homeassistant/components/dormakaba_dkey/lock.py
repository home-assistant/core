"""Dormakaba dKey integration lock platform."""
from __future__ import annotations

from typing import Any

from py_dormakaba_dkey import DKEYLock
from py_dormakaba_dkey.commands import Notifications, UnlockStatus

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN
from .models import DormakabaDkeyData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the lock platform for Dormakaba dKey."""
    data: DormakabaDkeyData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DormakabaDkeyLock(data.coordinator, data.lock)])


class DormakabaDkeyLock(CoordinatorEntity[DataUpdateCoordinator[None]], LockEntity):
    """Representation of Dormakaba dKey lock."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: DataUpdateCoordinator[None], lock: DKEYLock
    ) -> None:
        """Initialize a Dormakaba dKey lock."""
        super().__init__(coordinator)
        self._lock = lock
        self._attr_unique_id = lock.address
        self._attr_device_info = DeviceInfo(
            name=lock.device_info.device_name or lock.device_info.device_id,
            model="MTL 9291",
            sw_version=lock.device_info.sw_version,
            connections={(dr.CONNECTION_BLUETOOTH, lock.address)},
        )
        self._async_update_attrs()

    @callback
    def _async_update_attrs(self) -> None:
        """Handle updating _attr values."""
        self._attr_is_locked = self._lock.state.unlock_status in (
            UnlockStatus.LOCKED,
            UnlockStatus.SECURITY_LOCKED,
        )

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        await self._lock.lock()

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        await self._lock.unlock()

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
