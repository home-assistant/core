"""ISEO BLE Lock entity."""

from datetime import datetime
from typing import Any, override

from bleak import BleakError
from iseo_argo_ble import IseoAuthError, IseoConnectionError

from homeassistant.components.lock import LockEntity
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later

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
        self._cancel_relock: CALLBACK_TYPE | None = None
        self._applied_poll = 0
        # Set between an unlock and the reading that verifies it: the latch is
        # open but a door sensor still reports the door closed.
        self._awaiting_relock_poll = False
        # Unknown until the first successful read: the lock is only known to be
        # latched once it reports its door status.
        self._attr_is_locked: bool | None = None
        self._attr_is_unlocking = False

    @override
    async def async_added_to_hass(self) -> None:
        """Register the relock teardown."""
        await super().async_added_to_hass()
        self.async_on_remove(self._cancel_pending_relock)

    @callback
    def _cancel_pending_relock(self) -> None:
        """Cancel a relock that has not fired yet."""
        if self._cancel_relock:
            self._cancel_relock()
            self._cancel_relock = None

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Apply a fresh reading from the lock, or just its availability."""
        self._async_update_firmware_version()
        self._async_apply_reading()
        self.async_write_ha_state()

    @callback
    def _async_apply_reading(self) -> None:
        """Apply the last reading, unless it has been applied already.

        Listeners also fire on every advertisement and when the lock goes away,
        neither of which carries a reading. Re-applying the one already on file
        then would undo an unlock before the lock has re-latched.
        """
        state = self.coordinator.data
        if state is None or self._applied_poll == self.coordinator.poll_count:
            return
        self._applied_poll = self.coordinator.poll_count
        if self._awaiting_relock_poll:
            return

        if state.door_closed is None:
            # Without a door sensor the state can only ever be assumed: the
            # lock re-latches on its own after every unlock.
            self._attr_assumed_state = True
            door_closed = True
        else:
            door_closed = state.door_closed

        if not self._attr_is_unlocking:
            self._attr_is_locked = door_closed

    @callback
    def _set_locked(self) -> None:
        """Assume the lock has re-latched."""
        self._attr_is_unlocking = False
        self._awaiting_relock_poll = False
        self._attr_is_locked = True
        self.async_write_ha_state()

    async def _async_relock(self, _now: datetime) -> None:
        """Read the door once the latch has had time to re-engage."""
        self._cancel_relock = None
        self._awaiting_relock_poll = False
        # Support is unknown until a reading succeeds; try to take one rather
        # than assume the door has closed behind an unlock.
        if self.coordinator.door_status_supported is not False:
            if await self.coordinator.async_poll_now():
                return
            # The poll took no reading, so fall back to the lock's own
            # re-latching behaviour.
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
        self._cancel_pending_relock()

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
        self._awaiting_relock_poll = True
        self.async_write_ha_state()
        # A lock with no door to read only needs time to re-latch; one with a
        # door sensor is read as soon as the latch has re-engaged.
        delay = (
            RELOCK_DELAY
            if self.coordinator.door_status_supported is False
            else RELOCK_POLL_DELAY
        )
        self._cancel_relock = async_call_later(self.hass, delay, self._async_relock)
