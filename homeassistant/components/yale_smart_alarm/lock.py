"""Lock for Yale Alarm."""

from __future__ import annotations

from typing import Any

from yalesmartalarmclient import YaleLock, YaleLockState

from homeassistant.components.lock import LockEntity, LockState
from homeassistant.const import ATTR_CODE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import YaleConfigEntry
from .const import (
    CONF_LOCK_CODE_DIGITS,
    DEFAULT_LOCK_CODE_DIGITS,
    DOMAIN,
    YALE_ALL_ERRORS,
)
from .coordinator import YaleDataUpdateCoordinator
from .entity import YaleLockEntity

LOCK_STATE_MAP = {
    YaleLockState.LOCKED: LockState.LOCKED,
    YaleLockState.UNLOCKED: LockState.UNLOCKED,
    YaleLockState.DOOR_OPEN: LockState.OPEN,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: YaleConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Yale lock entry."""

    coordinator = entry.runtime_data
    code_format = entry.options.get(CONF_LOCK_CODE_DIGITS, DEFAULT_LOCK_CODE_DIGITS)

    async_add_entities(
        YaleDoorlock(coordinator, lock, code_format) for lock in coordinator.locks
    )


class YaleDoorlock(YaleLockEntity, LockEntity):
    """Representation of a Yale doorlock."""

    _attr_name = None

    def __init__(
        self, coordinator: YaleDataUpdateCoordinator, lock: YaleLock, code_format: int
    ) -> None:
        """Initialize the Yale Lock Device."""
        super().__init__(coordinator, lock)
        self._attr_code_format = rf"^\d{{{code_format}}}$"

    async def async_unlock(self, **kwargs: Any) -> None:
        """Send unlock command."""
        code: str | None = kwargs.get(ATTR_CODE)
        return await self.async_set_lock(YaleLockState.UNLOCKED, code)

    async def async_lock(self, **kwargs: Any) -> None:
        """Send lock command."""
        return await self.async_set_lock(YaleLockState.LOCKED, None)

    async def async_set_lock(self, state: YaleLockState, code: str | None) -> None:
        """Set lock."""
        if state is YaleLockState.UNLOCKED and not code:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_code",
            )

        lock_state = False
        try:
            if state is YaleLockState.LOCKED:
                lock_state = await self.hass.async_add_executor_job(
                    self.lock_data.close
                )
            if code and state is YaleLockState.UNLOCKED:
                lock_state = await self.hass.async_add_executor_job(
                    self.lock_data.open, code
                )
        except YALE_ALL_ERRORS as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_lock",
                translation_placeholders={
                    "name": self.lock_data.name,
                    "error": str(error),
                },
            ) from error

        if lock_state:
            self.lock_data.set_state(state)
            self.async_write_ha_state()
            return
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="could_not_change_lock",
        )

    @property
    def is_locked(self) -> bool | None:
        """Return true if the lock is locked."""
        return LOCK_STATE_MAP.get(self.lock_data.state()) == LockState.LOCKED

    @property
    def is_open(self) -> bool | None:
        """Return true if the lock is open."""
        return LOCK_STATE_MAP.get(self.lock_data.state()) == LockState.OPEN
