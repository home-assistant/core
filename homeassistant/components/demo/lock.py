"""Demo lock platform that implements locks."""

from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.components.lock import LockEntity, LockEntityFeature, LockState
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

LOCK_UNLOCK_DELAY = 2  # Used to give a realistic lock/unlock experience in frontend


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Demo config entry."""
    async_add_entities(
        [
            DemoLock("Front Door", LockState.LOCKED),
            DemoLock("Kitchen Door", LockState.UNLOCKED),
            DemoLock("Poorly Installed Door", LockState.UNLOCKED, False, True),
            DemoLock("Openable Lock", LockState.LOCKED, True),
        ]
    )


class DemoLock(LockEntity):
    """Representation of a Demo lock."""

    _attr_should_poll = False

    def __init__(
        self,
        name: str,
        state: str,
        openable: bool = False,
        jam_on_operation: bool = False,
    ) -> None:
        """Initialize the lock."""
        self._attr_name = name
        if openable:
            self._attr_supported_features = LockEntityFeature.OPEN
        self._state = state
        self._openable = openable
        self._jam_on_operation = jam_on_operation

    @property
    def is_locking(self) -> bool:
        """Return true if lock is locking."""
        return self._state == LockState.LOCKING

    @property
    def is_unlocking(self) -> bool:
        """Return true if lock is unlocking."""
        return self._state == LockState.UNLOCKING

    @property
    def is_jammed(self) -> bool:
        """Return true if lock is jammed."""
        return self._state == LockState.JAMMED

    @property
    def is_locked(self) -> bool:
        """Return true if lock is locked."""
        return self._state == LockState.LOCKED

    @property
    def is_open(self) -> bool:
        """Return true if lock is open."""
        return self._state == LockState.OPEN

    @property
    def is_opening(self) -> bool:
        """Return true if lock is opening."""
        return self._state == LockState.OPENING

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the device."""
        self._state = LockState.LOCKING
        self.async_write_ha_state()
        await asyncio.sleep(LOCK_UNLOCK_DELAY)
        if self._jam_on_operation:
            self._state = LockState.JAMMED
        else:
            self._state = LockState.LOCKED
        self.async_write_ha_state()

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the device."""
        self._state = LockState.UNLOCKING
        self.async_write_ha_state()
        await asyncio.sleep(LOCK_UNLOCK_DELAY)
        self._state = LockState.UNLOCKED
        self.async_write_ha_state()

    async def async_open(self, **kwargs: Any) -> None:
        """Open the door latch."""
        self._state = LockState.OPENING
        self.async_write_ha_state()
        await asyncio.sleep(LOCK_UNLOCK_DELAY)
        self._state = LockState.OPEN
        self.async_write_ha_state()
