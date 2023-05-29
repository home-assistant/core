"""Platform for Schlage lock integration."""
from __future__ import annotations

from typing import Any

from pyschlage import Schlage
from pyschlage.lock import Lock

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MANUFACTURER


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Schlage WiFi locks based on a config entry."""
    api: Schlage = hass.data[DOMAIN][config_entry.entry_id]
    locks: list[Lock] = await hass.async_add_executor_job(api.locks)
    async_add_entities([SchlageLock(lock) for lock in locks])


class SchlageLock(LockEntity):
    """Schlage lock entity."""

    def __init__(self, lock: Lock) -> None:
        """Initialize a Schlage Lock."""
        super().__init__()
        self._lock: Lock = lock
        self.device_id: str = lock.device_id
        self._attr_unique_id = lock.device_id
        self._update_attrs()

    def update(self) -> None:
        """Fetch new state data for this lock."""
        self._lock.refresh()
        self._update_attrs()

    def _update_attrs(self) -> None:
        self._attr_name = self._lock.name
        # When is_locked is None the lock is unavailable.
        self._attr_available = self._lock.is_locked is not None
        self._attr_is_locked = self._lock.is_locked
        self._attr_is_jammed = self._lock.is_jammed
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.device_id)},
            name=self._attr_name,
            manufacturer=MANUFACTURER,
            model=self._lock.model_name,
            sw_version=self._lock.firmware_version,
        )

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the device."""
        await self.hass.async_add_executor_job(self._lock.lock)

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the device."""
        await self.hass.async_add_executor_job(self._lock.unlock)
