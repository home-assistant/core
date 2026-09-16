"""ISEO BLE Lock entity."""

import asyncio
from typing import Any, override

from bleak import BleakError
from iseo_argo_ble import IseoAuthError, IseoConnectionError

from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, GATEWAY_NAME, RELOCK_DELAY, RELOCK_POLL_DELAY
from .coordinator import IseoConfigEntry, IseoCoordinator
from .entity import IseoEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IseoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ISEO lock entity from a config entry."""
    async_add_entities([IseoLockEntity(entry.runtime_data)])


class IseoLockEntity(IseoEntity, LockEntity):
    """Represents an ISEO X1R BLE door lock.

    The X1R is a momentary latch release: it re-latches by itself a couple of
    seconds after being opened, so there is no way to lock it on demand and
    `async_lock` always raises. `unlock` (rather than `LockEntityFeature.OPEN`)
    is used for the release because the lock stays engaged in the door frame
    and the physical door itself is never operated.
    """

    _attr_name = None  # entity name = device name

    def __init__(self, coordinator: IseoCoordinator) -> None:
        """Initialize the lock entity."""
        super().__init__(coordinator)
        self._attr_unique_id = coordinator.config_entry.unique_id
        self._relock_task: asyncio.Task[None] | None = None
        # Unknown until the first successful read: the lock is only known to be
        # latched once it reports its door status.
        self._attr_is_locked: bool | None = None
        self._attr_is_unlocking = False

    @override
    async def async_added_to_hass(self) -> None:
        """Register the relock task teardown."""
        await super().async_added_to_hass()
        self.async_on_remove(self._cancel_relock_task)

    @callback
    def _cancel_relock_task(self) -> None:
        """Cancel any pending relock task."""
        if self._relock_task and not self._relock_task.done():
            self._relock_task.cancel()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Apply a fresh reading from the lock."""
        self._async_update_firmware_version()

        if (state := self.coordinator.data) is None:
            return

        if state.door_closed is None:
            # Without a door sensor the state can only ever be assumed: the
            # lock re-latches on its own after every unlock.
            self._attr_assumed_state = True
            self._attr_is_locked = True
        elif not self._attr_is_unlocking:
            self._attr_is_locked = state.door_closed

        self.async_write_ha_state()

    @callback
    def _set_locked(self) -> None:
        """Assume the lock has re-latched."""
        self._attr_is_unlocking = False
        self._attr_is_locked = True
        self.async_write_ha_state()

    async def _auto_relock(self) -> None:
        """Revert to 'locked' after the motor has re-latched."""
        if self.coordinator.door_status_supported:
            await asyncio.sleep(RELOCK_POLL_DELAY)
            if await self.coordinator.async_poll_now():
                return
            # The poll took no reading, so fall back to the lock's own
            # re-latching behaviour.
        else:
            await asyncio.sleep(RELOCK_DELAY)
        self._set_locked()

    @override
    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the door (not supported)."""
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="lock_not_supported",
        )

    @override
    async def async_unlock(self, **kwargs: Any) -> None:
        """Open the lock (momentary actuator — always re-latches automatically)."""
        self._cancel_relock_task()

        self._attr_is_locked = False
        self._attr_is_unlocking = True
        self.async_write_ha_state()

        try:
            async with self.coordinator.connection_lock:
                await self.coordinator.client.gw_open(remote_user_name=GATEWAY_NAME)
        except IseoAuthError as exc:
            self._set_locked()
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="lock_rejected_identity",
            ) from exc
        except (IseoConnectionError, BleakError, TimeoutError, OSError) as exc:
            self._set_locked()
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from exc

        self._attr_is_unlocking = False
        self.async_write_ha_state()
        self._relock_task = self.hass.async_create_task(self._auto_relock())
