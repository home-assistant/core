"""Dormakaba dKey integration lock platform."""

from __future__ import annotations

from typing import Any

from py_dormakaba_dkey.commands import UnlockStatus

from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DormakabaDkeyConfigEntry, DormakabaDkeyCoordinator
from .entity import DormakabaDkeyEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DormakabaDkeyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the lock platform for Dormakaba dKey."""
    async_add_entities([DormakabaDkeyLock(entry.runtime_data)])


class DormakabaDkeyLock(DormakabaDkeyEntity, LockEntity):
    """Representation of Dormakaba dKey lock."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: DormakabaDkeyCoordinator) -> None:
        """Initialize a Dormakaba dKey lock."""
        self._attr_unique_id = coordinator.lock.address
        super().__init__(coordinator)

    @callback
    def _async_update_attrs(self) -> None:
        """Handle updating _attr values."""
        self._attr_is_locked = self.coordinator.lock.state.unlock_status in (
            UnlockStatus.LOCKED,
            UnlockStatus.SECURITY_LOCKED,
        )

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        await self.coordinator.lock.lock()

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        await self.coordinator.lock.unlock()
