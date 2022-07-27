"""Support for Yale Access Bluetooth locks."""
from __future__ import annotations

from typing import Any

from yalexs_ble import LockState, LockStatus

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .models import YaleXSBLEData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up locks."""
    data: YaleXSBLEData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([YaleXSBLELock(data)])


class YaleXSBLELock(LockEntity):
    """A yale xs ble lock."""

    def __init__(self, data: YaleXSBLEData) -> None:
        """Initialize a the lock."""
        self._data = data
        self.device = data.lock
        self._attr_name = f"{data.local_name} Lock"
        self._attr_available = False
        self._attr_unique_id = data.local_name
        self._attr_device_info = DeviceInfo(
            name=data.local_name,
            manufacturer="Yale",
            identifiers={(DOMAIN, data.local_name)},
        )

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(self.device.register_callback(self._async_update))
        return await super().async_added_to_hass()

    @callback
    def _async_update(self, new_state: LockState) -> None:
        self._attr_available = True
        self._attr_is_locked = False
        self._attr_is_locking = False
        self._attr_is_unlocking = False
        self._attr_is_jammed = False
        lock_state = new_state.lock
        if lock_state == LockStatus.LOCKED:
            self._attr_is_locked = True
        elif lock_state == LockStatus.LOCKING:
            self._attr_is_locking = True
        elif lock_state == LockStatus.UNLOCKING:
            self._attr_is_unlocking = True
        elif lock_state in (
            LockStatus.UNKNOWN_01,
            LockStatus.UNKNOWN_06,
        ):
            self._attr_is_jammed = True

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        return await self.device.unlock()

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        return await self.device.lock()
