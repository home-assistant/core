"""Support for ESPHome locks."""

from __future__ import annotations

from functools import partial
from typing import Any

from aioesphomeapi import EntityInfo, LockCommand, LockEntityState, LockInfo, LockState

from homeassistant.components.lock import LockEntity, LockEntityFeature
from homeassistant.const import ATTR_CODE
from homeassistant.core import callback

from .entity import (
    EsphomeEntity,
    convert_api_error_ha_error,
    esphome_state_property,
    platform_async_setup_entry,
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
        return self._state.state is LockState.LOCKED

    @property
    @esphome_state_property
    def is_locking(self) -> bool | None:
        """Return true if the lock is locking."""
        return self._state.state is LockState.LOCKING

    @property
    @esphome_state_property
    def is_unlocking(self) -> bool | None:
        """Return true if the lock is unlocking."""
        return self._state.state is LockState.UNLOCKING

    @property
    @esphome_state_property
    def is_jammed(self) -> bool | None:
        """Return true if the lock is jammed (incomplete locking)."""
        return self._state.state is LockState.JAMMED

    @convert_api_error_ha_error
    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        self._client.lock_command(self._key, LockCommand.LOCK)

    @convert_api_error_ha_error
    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        code = kwargs.get(ATTR_CODE, None)
        self._client.lock_command(self._key, LockCommand.UNLOCK, code)

    @convert_api_error_ha_error
    async def async_open(self, **kwargs: Any) -> None:
        """Open the door latch."""
        self._client.lock_command(self._key, LockCommand.OPEN)


async_setup_entry = partial(
    platform_async_setup_entry,
    info_type=LockInfo,
    entity_type=EsphomeLock,
    state_type=LockEntityState,
)
