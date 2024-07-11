"""Demo lock platform that implements locks."""

from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.components.lock import LockEntity, LockEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_JAMMED,
    STATE_LOCKED,
    STATE_LOCKING,
    STATE_OPEN,
    STATE_OPENING,
    STATE_UNLOCKED,
    STATE_UNLOCKING,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

LOCK_UNLOCK_DELAY = 2  # Used to give a realistic lock/unlock experience in frontend


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Demo config entry."""
    async_add_entities(
        [
            DemoLock("Front Door", STATE_LOCKED),
            DemoLock("Kitchen Door", STATE_UNLOCKED),
            DemoLock("Poorly Installed Door", STATE_UNLOCKED, False, True),
            DemoLock("Openable Lock", STATE_LOCKED, True),
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
        return self._state == STATE_LOCKING

    @property
    def is_unlocking(self) -> bool:
        """Return true if lock is unlocking."""
        return self._state == STATE_UNLOCKING

    @property
    def is_jammed(self) -> bool:
        """Return true if lock is jammed."""
        return self._state == STATE_JAMMED

    @property
    def is_locked(self) -> bool:
        """Return true if lock is locked."""
        return self._state == STATE_LOCKED

    @property
    def is_open(self) -> bool:
        """Return true if lock is open."""
        return self._state == STATE_OPEN

    @property
    def is_opening(self) -> bool:
        """Return true if lock is opening."""
        return self._state == STATE_OPENING

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the device."""
        self._state = STATE_LOCKING
        self.async_write_ha_state()
        await asyncio.sleep(LOCK_UNLOCK_DELAY)
        if self._jam_on_operation:
            self._state = STATE_JAMMED
        else:
            self._state = STATE_LOCKED
        self.async_write_ha_state()

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the device."""
        self._state = STATE_UNLOCKING
        self.async_write_ha_state()
        await asyncio.sleep(LOCK_UNLOCK_DELAY)
        self._state = STATE_UNLOCKED
        self.async_write_ha_state()

    async def async_open(self, **kwargs: Any) -> None:
        """Open the door latch."""
        self._state = STATE_OPENING
        self.async_write_ha_state()
        await asyncio.sleep(LOCK_UNLOCK_DELAY)
        self._state = STATE_OPEN
        self.async_write_ha_state()
