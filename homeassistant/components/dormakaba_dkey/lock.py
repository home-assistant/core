"""Dormakaba dKey integration lock platform."""
from __future__ import annotations

from typing import Any

from py_dormakaba_dkey import DKEYLock
from py_dormakaba_dkey.commands import UnlockStatus

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .entity import DormakabaDkeyEntity
from .models import DormakabaDkeyData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the lock platform for Dormakaba dKey."""
    data: DormakabaDkeyData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DormakabaDkeyLock(data.coordinator, data.lock)])


class DormakabaDkeyLock(DormakabaDkeyEntity, LockEntity):
    """Representation of Dormakaba dKey lock."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: DataUpdateCoordinator[None], lock: DKEYLock
    ) -> None:
        """Initialize a Dormakaba dKey lock."""
        self._attr_unique_id = lock.address
        super().__init__(coordinator, lock)

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
