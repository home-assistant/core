"""Lock platform for Nest."""

from __future__ import annotations

from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import NestConfigEntry
from .entity import NestEntity
from .pynest.enums import LockBoltState
from .pynest.models import NestLock

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NestConfigEntry,
    async_add_devices: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Nest lock platform from a config entry."""
    coordinator = entry.runtime_data
    entities = [
        NestLockEntity(coordinator, device)
        for device in coordinator.data.values()
        if isinstance(device, NestLock)
    ]
    async_add_devices(entities)


class NestLockEntity(NestEntity[NestLock], LockEntity):
    """Representation of a Nest Lock."""

    _attr_name = None  # The lock is the main feature of the device

    @property
    def is_locked(self) -> bool:
        """Return true if lock is locked."""
        return self.device.bolt_state == LockBoltState.LOCKED

    @property
    def is_locking(self) -> bool:
        """Return true if lock is locking."""
        return self.device.bolt_state == LockBoltState.LOCKING

    @property
    def is_unlocking(self) -> bool:
        """Return true if lock is unlocking."""
        return self.device.bolt_state == LockBoltState.UNLOCKING

    @property
    def is_jammed(self) -> bool:
        """Return true if lock is jammed."""
        return self.device.bolt_state == LockBoltState.JAMMED

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        await self._set_device_data({"bolt_locked": True})

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        await self._set_device_data({"bolt_locked": False})
