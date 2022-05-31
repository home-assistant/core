"""LOQED lock integration for Home Assistant."""
from __future__ import annotations

from typing import Any

from loqedAPI import loqed

from homeassistant.components.lock import LockEntity, LockEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_JAMMED,
    STATE_LOCKED,
    STATE_LOCKING,
    STATE_UNKNOWN,
    STATE_UNLOCKED,
    STATE_UNLOCKING,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LoqedDataCoordinator
from .const import CONF_COORDINATOR, CONF_LOCK, DOMAIN

LOCK_STATES = {
    "latch": STATE_UNLOCKED,
    "night_lock": STATE_LOCKED,
    "open": STATE_UNLOCKED,
    "day_lock": STATE_UNLOCKED,
    "unknown": STATE_UNKNOWN,
}

LOCK_GO_TO_STATES = {
    "latch": STATE_UNLOCKING,
    "night_lock": STATE_LOCKING,
    "open": STATE_UNLOCKING,
    "day_lock": STATE_UNLOCKING,
    "unknown": STATE_UNKNOWN,
}


WEBHOOK_API_ENDPOINT = "/api/loqed/webhook"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Loqed lock platform."""
    entry_state = hass.data[DOMAIN][entry.entry_id]
    lock = entry_state[CONF_LOCK]
    coordinator = entry_state[CONF_COORDINATOR]

    async_add_entities([LoqedLock(lock, coordinator)])


class LoqedLock(CoordinatorEntity[LoqedDataCoordinator], LockEntity):
    """Representation of a loqed lock."""

    def __init__(self, lock: loqed.Lock, coordinator: LoqedDataCoordinator) -> None:
        """Initialize the lock."""
        super().__init__(coordinator)
        self._lock = lock
        self._attr_unique_id = self._lock.id
        self._attr_name = self._lock.name
        self._attr_supported_features = LockEntityFeature.OPEN
        self._state = STATE_UNKNOWN
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, lock.id)},
            name="Loqed instance",
        )

    @property
    def changed_by(self):
        """Return true if lock is locking."""
        return "KeyID " + str(self._lock.last_key_id)

    @property
    def is_locking(self):
        """Return true if lock is locking."""
        return self._state == STATE_LOCKING

    @property
    def is_unlocking(self):
        """Return true if lock is unlocking."""
        return self._state == STATE_UNLOCKING

    @property
    def is_jammed(self):
        """Return true if lock is jammed."""
        return self._state == STATE_JAMMED

    @property
    def is_locked(self):
        """Return true if lock is locked."""
        return self._state == STATE_LOCKED

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        self._state = STATE_LOCKING
        self.async_write_ha_state()

        await self._lock.lock()

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        self._state = STATE_UNLOCKING
        self.async_write_ha_state()

        await self._lock.unlock()

    async def async_open(self, **kwargs: Any) -> None:
        """Open the door latch."""
        self._state = STATE_UNLOCKING
        self.async_write_ha_state()

        await self._lock.open()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data

        if "requested_state" in data and data["requested_state"].lower() in LOCK_STATES:
            self._state = LOCK_STATES[data["requested_state"].lower()]
            self.async_schedule_update_ha_state()
        elif "go_to_state" in data and data["go_to_state"].lower() in LOCK_GO_TO_STATES:
            self._state = LOCK_GO_TO_STATES[data["go_to_state"].lower()]
            self.async_schedule_update_ha_state()
        elif "bolt_state" in data and data["bolt_state"] in LOCK_STATES:
            self._state = LOCK_STATES[data["bolt_state"]]
            self.async_schedule_update_ha_state()
