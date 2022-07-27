"""Support for Yale Access Bluetooth locks."""
from __future__ import annotations

from typing import Any

from yalexs_ble import LockState, LockStatus

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

    _attr_has_entity_name = True
    _attr_name = "Lock"

    @callback
    def _async_update_callback(self, new_state: LockState) -> None:
        """Update the state."""
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
        super()._async_update_callback(new_state)

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        return await self._device.unlock()

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        return await self._device.lock()
