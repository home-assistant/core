"""Support for SimpliSafe locks."""
from __future__ import annotations

from typing import Any

from simplipy.device.lock import Lock, LockStates
from simplipy.errors import SimplipyError
from simplipy.system.v3 import SystemV3
from simplipy.websocket import EVENT_LOCK_LOCKED, EVENT_LOCK_UNLOCKED, WebsocketEvent

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SimpliSafe, SimpliSafeEntity
from .const import DOMAIN, LOGGER

ATTR_LOCK_LOW_BATTERY = "lock_low_battery"
ATTR_PIN_PAD_LOW_BATTERY = "pin_pad_low_battery"

STATE_MAP_FROM_WEBSOCKET_EVENT = {
    EVENT_LOCK_LOCKED: True,
    EVENT_LOCK_UNLOCKED: False,
}

WEBSOCKET_EVENTS_TO_LISTEN_FOR = (EVENT_LOCK_LOCKED, EVENT_LOCK_UNLOCKED)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up SimpliSafe locks based on a config entry."""
    simplisafe = hass.data[DOMAIN][entry.entry_id]
    locks = []

    for system in simplisafe.systems.values():
        if system.version == 2:
            LOGGER.info("Skipping lock setup for V2 system: %s", system.system_id)
            continue

        for lock in system.locks.values():
            locks.append(SimpliSafeLock(simplisafe, system, lock))

    async_add_entities(locks)


class SimpliSafeLock(SimpliSafeEntity, LockEntity):
    """Define a SimpliSafe lock."""

    def __init__(self, simplisafe: SimpliSafe, system: SystemV3, lock: Lock) -> None:
        """Initialize."""
        super().__init__(
            simplisafe,
            system,
            device=lock,
            additional_websocket_events=WEBSOCKET_EVENTS_TO_LISTEN_FOR,
        )

        self._device: Lock

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        try:
            await self._device.async_lock()
        except SimplipyError as err:
            raise HomeAssistantError(
                f'Error while locking "{self._device.name}": {err}'
            ) from err

        self._attr_is_locked = True
        self.async_write_ha_state()

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        try:
            await self._device.async_unlock()
        except SimplipyError as err:
            raise HomeAssistantError(
                f'Error while unlocking "{self._device.name}": {err}'
            ) from err

        self._attr_is_locked = False
        self.async_write_ha_state()

    @callback
    def async_update_from_rest_api(self) -> None:
        """Update the entity with the provided REST API data."""
        self._attr_is_jammed = self._device.state == LockStates.JAMMED
        self._attr_is_locked = self._device.state == LockStates.LOCKED

        self._attr_extra_state_attributes.update(
            {
                ATTR_LOCK_LOW_BATTERY: self._device.lock_low_battery,
                ATTR_PIN_PAD_LOW_BATTERY: self._device.pin_pad_low_battery,
            }
        )

    @callback
    def async_update_from_websocket_event(self, event: WebsocketEvent) -> None:
        """Update the entity when new data comes from the websocket."""
        assert event.event_type

        if state := STATE_MAP_FROM_WEBSOCKET_EVENT.get(event.event_type) is not None:
            self._attr_is_locked = state
            self.async_reset_error_count()
        else:
            LOGGER.error("Unknown lock websocket event: %s", event.event_type)
            self.async_increment_error_count()
