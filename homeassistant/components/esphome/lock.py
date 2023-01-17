"""Support for ESPHome locks."""
from __future__ import annotations

from typing import Any

from aioesphomeapi import LockCommand, LockEntityState, LockInfo, LockState

from homeassistant.components.lock import LockEntity, LockEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_CODE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EsphomeEntity, esphome_state_property, platform_async_setup_entry


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up ESPHome switches based on a config entry."""
    await platform_async_setup_entry(
        hass,
        entry,
        async_add_entities,
        component_key="lock",
        info_type=LockInfo,
        entity_type=EsphomeLock,
        state_type=LockEntityState,
    )


class EsphomeLock(EsphomeEntity[LockInfo, LockEntityState], LockEntity):
    """A lock implementation for ESPHome."""

    @property
    def assumed_state(self) -> bool:
        """Return True if unable to access real state of the entity."""
        return self._static_info.assumed_state

    @property
    def supported_features(self) -> LockEntityFeature:
        """Flag supported features."""
        if self._static_info.supports_open:
            return LockEntityFeature.OPEN
        return LockEntityFeature(0)

    @property
    def code_format(self) -> str | None:
        """Regex for code format or None if no code is required."""
        if self._static_info.requires_code:
            return self._static_info.code_format
        return None

    @property
    @esphome_state_property
    def is_locked(self) -> bool | None:
        """Return true if the lock is locked."""
        return self._state.state == LockState.LOCKED

    @property
    @esphome_state_property
    def is_locking(self) -> bool | None:
        """Return true if the lock is locking."""
        return self._state.state == LockState.LOCKING

    @property
    @esphome_state_property
    def is_unlocking(self) -> bool | None:
        """Return true if the lock is unlocking."""
        return self._state.state == LockState.UNLOCKING

    @property
    @esphome_state_property
    def is_jammed(self) -> bool | None:
        """Return true if the lock is jammed (incomplete locking)."""
        return self._state.state == LockState.JAMMED

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        await self._client.lock_command(self._static_info.key, LockCommand.LOCK)

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        code = kwargs.get(ATTR_CODE, None)
        await self._client.lock_command(self._static_info.key, LockCommand.UNLOCK, code)

    async def async_open(self, **kwargs: Any) -> None:
        """Open the door latch."""
        await self._client.lock_command(self._static_info.key, LockCommand.OPEN)
