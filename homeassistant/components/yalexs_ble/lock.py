"""Support for Yale Access Bluetooth locks."""

from __future__ import annotations

from typing import Any

from yalexs_ble import ConnectionInfo, LockInfo, LockState, LockStatus

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import YALEXSBLEEntity
from .models import YaleXSBLEData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up locks."""
    data: YaleXSBLEData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([YaleXSBLELock(data)])


class YaleXSBLELock(YALEXSBLEEntity, LockEntity):
    """A yale xs ble lock."""

    _attr_name = None

    @callback
    def _async_update_state(
        self, new_state: LockState, lock_info: LockInfo, connection_info: ConnectionInfo
    ) -> None:
        """Update the state."""
        self._attr_is_locked = False
        self._attr_is_locking = False
        self._attr_is_unlocking = False
        self._attr_is_jammed = False
        lock_state = new_state.lock
        if lock_state is LockStatus.LOCKED:
            self._attr_is_locked = True
        elif lock_state is LockStatus.LOCKING:
            self._attr_is_locking = True
        elif lock_state is LockStatus.UNLOCKING:
            self._attr_is_unlocking = True
        elif lock_state in (
            LockStatus.UNKNOWN_01,
            LockStatus.UNKNOWN_06,
        ):
            self._attr_is_jammed = True
        elif lock_state is LockStatus.UNKNOWN:
            self._attr_is_locked = None
        super()._async_update_state(new_state, lock_info, connection_info)

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        await self._device.unlock()

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        await self._device.lock()
