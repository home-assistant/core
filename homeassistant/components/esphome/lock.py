"""Support for ESPHome locks."""
from __future__ import annotations

from typing import Any

from aioesphomeapi import EntityInfo, LockCommand, LockEntityState, LockInfo, LockState

from homeassistant.components.lock import LockEntity, LockEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_CODE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import (
    EsphomeEntity,
    esphome_state_property,
    platform_async_setup_entry,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up ESPHome switches based on a config entry."""
    await platform_async_setup_entry(
        hass,
        entry,
        async_add_entities,
        info_type=LockInfo,
        entity_type=EsphomeLock,
        state_type=LockEntityState,
    )


class EsphomeLock(EsphomeEntity[LockInfo, LockEntityState], LockEntity):
    """A lock implementation for ESPHome."""

    @callback
    def _on_static_info_update(self, static_info: EntityInfo) -> None:
        """Set attrs from static info."""
        super()._on_static_info_update(static_info)
        static_info = self._static_info
        self._attr_assumed_state = static_info.assumed_state
        self._attr_supported_features = LockEntityFeature(0)
        if static_info.supports_open:
            self._attr_supported_features |= LockEntityFeature.OPEN
        if static_info.requires_code:
            self._attr_code_format = static_info.code_format
        else:
            self._attr_code_format = None

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
        await self._client.lock_command(self._key, LockCommand.LOCK)

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        code = kwargs.get(ATTR_CODE, None)
        await self._client.lock_command(self._key, LockCommand.UNLOCK, code)

    async def async_open(self, **kwargs: Any) -> None:
        """Open the door latch."""
        await self._client.lock_command(self._key, LockCommand.OPEN)
