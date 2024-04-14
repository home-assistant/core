"""LOQED lock integration for Home Assistant."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.lock import LockEntity, LockEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LoqedDataCoordinator
from .const import DOMAIN
from .entity import LoqedEntity

WEBHOOK_API_ENDPOINT = "/api/loqed/webhook"

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Loqed lock platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([LoqedLock(coordinator)])


class LoqedLock(LoqedEntity, LockEntity):
    """Representation of a loqed lock."""

    _attr_supported_features = LockEntityFeature.OPEN

    def __init__(self, coordinator: LoqedDataCoordinator) -> None:
        """Initialize the lock."""
        super().__init__(coordinator)
        self._lock = coordinator.lock
        self._attr_unique_id = self._lock.id
        self._attr_name = None

    @property
    def changed_by(self) -> str:
        """Return internal ID of last used key."""
        return f"KeyID {self._lock.last_key_id}"

    @property
    def is_locking(self) -> bool | None:
        """Return true if lock is locking."""
        return self._lock.bolt_state == "locking"

    @property
    def is_unlocking(self) -> bool | None:
        """Return true if lock is unlocking."""
        return self._lock.bolt_state == "unlocking"

    @property
    def is_jammed(self) -> bool | None:
        """Return true if lock is jammed."""
        return self._lock.bolt_state == "motor_stall"

    @property
    def is_locked(self) -> bool | None:
        """Return true if lock is locked."""
        return self._lock.bolt_state in ["night_lock_remote", "night_lock"]

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        await self._lock.lock()

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        await self._lock.unlock()

    async def async_open(self, **kwargs: Any) -> None:
        """Open the door latch."""
        await self._lock.open()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug(self.coordinator.data)
        if "bolt_state" in self.coordinator.data:
            self._lock.updateState(self.coordinator.data["bolt_state"]).close()
            self.async_write_ha_state()
