"""ISEO BLE Lock entity."""

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any, cast, override

from bleak.backends.device import BLEDevice
from iseo_argo_ble import (
    IseoAuthError,
    IseoClient,
    IseoConnectionError,
    LockState,
    parse_iseo_advertisement,
)

from homeassistant.components.bluetooth import (
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
    async_clear_advertisement_history,
    async_register_callback,
)
from homeassistant.components.bluetooth.match import BluetoothCallbackMatcher
from homeassistant.components.lock import LockEntity
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from . import IseoConfigEntry
from .const import CONF_ENABLE_POLLING, DOMAIN

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

# Seconds the entity stays in "unlocked" state before reverting to "locked".
_RELOCK_DELAY = 5

# Only used when the polling fallback is enabled; see CONF_ENABLE_POLLING.
_POLL_INTERVAL = timedelta(seconds=30)

# The lock advertises sparsely — minutes apart when nothing is happening — so
# silence only means it is gone after a good while.
_UNAVAILABLE_AFTER = timedelta(minutes=10)

_AVAILABILITY_CHECK_INTERVAL = timedelta(minutes=1)

# How often to re-read the capabilities of a lock that reported it has no
# door status. Door Status Advice can be switched on in the Argo app at any
# time and only shows up in a read, so the answer cannot be taken as final —
# but it changes about never, and each read wakes the lock.
_CAPABILITY_RECHECK = timedelta(hours=12)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IseoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ISEO lock entity from a config entry."""
    async_add_entities([IseoLockEntity(entry)])


class IseoLockEntity(LockEntity):
    """Represents an ISEO X1R BLE door lock.

    The X1R is a momentary latch release: it re-latches by itself a couple of
    seconds after being opened, so there is no way to lock it on demand and
    `async_lock` always raises. `unlock` (rather than `LockEntityFeature.OPEN`)
    is used for the release because the lock stays engaged in the door frame
    and the physical door itself is never operated.

    Door state comes from the lock's advertisements. Polling on a timer is
    available as an option for locks that cannot report door status passively.
    """

    _attr_has_entity_name = True
    _attr_name = None  # entity name = device name
    _attr_should_poll = False

    def __init__(
        self,
        entry: IseoConfigEntry,
    ) -> None:
        """Initialize the lock entity."""
        self._entry = entry
        self._relock_task: asyncio.Task[None] | None = None
        self._ble_lock = asyncio.Lock()
        self._door_status_supported: bool | None = None
        self._fw_version_set = False
        self.client: IseoClient = entry.runtime_data

        self._attr_unique_id = entry.unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, cast(str, entry.unique_id))},
            connections={(CONNECTION_BLUETOOTH, entry.data[CONF_ADDRESS])},
            manufacturer="ISEO",
            model="X1R Smart",
            model_id="X1R",
        )

        # Unknown until the first successful read: the lock is only known to be
        # latched once it reports its door status.
        self._attr_is_locked: bool | None = None
        self._attr_is_unlocking = False
        self._attr_available = True
        self._poll_suppress_until: datetime | None = None
        self._last_advertisement: datetime | None = None
        self._last_ble_device: BLEDevice | None = None
        self._initial_read: asyncio.Task[None] | None = None
        self._probed = False
        self._last_probe: datetime | None = None
        self._door_seen_open = False
        self._identity_rejected = False

    @override
    async def async_added_to_hass(self) -> None:
        """Start following the lock's advertisements.

        Nothing is read over a connection here. After a restart no scanner has
        seen the lock until it next advertises — minutes, on this hardware — so
        connecting at setup only stalls the platform and fails.
        """
        address = self._entry.data[CONF_ADDRESS]
        self.async_on_remove(
            async_register_callback(
                self.hass,
                self._async_handle_advertisement,
                BluetoothCallbackMatcher(address=address),
                BluetoothScanningMode.PASSIVE,
            )
        )
        self.async_on_remove(
            async_track_time_interval(
                self.hass, self._check_availability, _AVAILABILITY_CHECK_INTERVAL
            )
        )
        self.async_on_remove(
            async_track_time_interval(
                self.hass, self._async_poll_interval, _POLL_INTERVAL
            )
        )
        self.async_on_remove(self._cancel_relock_task)
        self.async_on_remove(self._cancel_initial_read)

    async def _async_poll_interval(self, _now: datetime) -> None:
        """Poll the lock on the configured interval, if the fallback is on.

        The option is read here rather than at setup because applying it by
        reloading the entry would stall: setup resolves the device through
        ``async_ble_device_from_address()``, which following the lock passively
        keeps empty.
        """
        if self._identity_rejected or not self._entry.options.get(
            CONF_ENABLE_POLLING, False
        ):
            # A rejected identity never recovers on its own, so polling on
            # would only wake the lock every 30s for a read that cannot work.
            return
        await self._poll_state()

    @callback
    def _async_handle_advertisement(
        self, service_info: BluetoothServiceInfoBleak, _change: BluetoothChange
    ) -> None:
        """Apply the door state the lock encodes in its advertisement."""
        self._last_advertisement = dt_util.utcnow()
        self._last_ble_device = service_info.device
        self._set_available(True)
        self._async_schedule_initial_read()

        # The lock encodes door state in the set of service UUIDs it advertises
        # rather than in changing payload bytes, so without resetting the
        # scanners' merge state the entity would never see the door close again.
        async_clear_advertisement_history(self.hass, self._entry.data[CONF_ADDRESS])

        if self._door_status_supported is False:
            # The lock reported it does not support door status. Advertisements
            # carry no capability flags, so the door bit in them is meaningless
            # here — hearing the lock is all this tells us.
            return

        state = parse_iseo_advertisement(list(service_info.service_uuids or []))
        if state is None or state.door_closed is None:
            _LOGGER.debug(
                "Advertisement carried no door state: %s", service_info.service_uuids
            )
            return

        _LOGGER.debug("Advertisement reports door_closed=%s", state.door_closed)
        self._door_status_supported = True
        self._attr_assumed_state = False

        self._apply_door_state(state.door_closed)

    @callback
    def _apply_door_state(self, door_closed: bool) -> None:
        """Apply a door reading, respecting the window after an unlock."""
        if (
            door_closed
            and not self._door_seen_open
            and (
                self._attr_is_unlocking
                or (
                    self._poll_suppress_until
                    and dt_util.utcnow() < self._poll_suppress_until
                )
            )
        ):
            # The lock keeps reporting "closed" for a moment after the latch is
            # released — while gw_open() is still in flight, and for a few
            # seconds after it returns — so that is not news. A close once the
            # door has been seen open is the door itself rather than that lag,
            # and is applied.
            return

        if not door_closed:
            # Never ignore the door opening: the next reading can be minutes
            # away, and the relock timer would otherwise leave the entity
            # locked with the door standing open.
            self._cancel_relock_task()
            self._poll_suppress_until = None

        self._door_seen_open = not door_closed
        self._attr_is_locked = door_closed
        self.async_write_ha_state()

    @callback
    def _check_availability(self, _now: datetime) -> None:
        """Mark the lock unavailable once its advertisements stop arriving.

        Runs on a timer and never connects to the lock. Clearing the manager's
        advertisement history to keep callbacks flowing also clears the data it
        tracks devices by, so recency is tracked here instead.
        """
        if self._last_advertisement is None:
            return
        if self._entry.options.get(CONF_ENABLE_POLLING, False):
            # Polling is the point of the fallback: it reports availability
            # itself, and would otherwise spend all day fighting this timer on
            # exactly the locks whose advertisements do not reach us.
            return
        if dt_util.utcnow() - self._last_advertisement >= _UNAVAILABLE_AFTER:
            self._set_available(False, "no advertisement received")

    def _cancel_relock_task(self) -> None:
        """Cancel any pending relock task."""
        if self._relock_task and not self._relock_task.done():
            self._relock_task.cancel()

    def _set_available(self, available: bool, reason: object = None) -> None:
        """Update availability, logging only when it actually changes."""
        if available and self._identity_rejected:
            # Hearing the lock says nothing about whether it still accepts our
            # identity, and that does not recover on its own. Staying available
            # would look healthy while every operation fails.
            return
        if self._attr_available == available:
            return
        if available:
            _LOGGER.info("Lock is back online")
        else:
            _LOGGER.info("Lock is unavailable: %s", reason)
        self._attr_available = available
        self.async_write_ha_state()

    def _reject_identity(self, exc: Exception) -> None:
        """Record that the lock refused the enrolled identity.

        Rejected credentials do not recover on their own: the gateway identity
        has to be enrolled on the lock again. Advertisements carry nothing
        about credentials, so the entity has to stay unavailable until it is —
        otherwise it looks healthy while every operation fails.
        """
        if not self._identity_rejected:
            _LOGGER.warning(
                "Lock rejected the Home Assistant identity (%s), delete the "
                "integration and set it up again to enroll it anew",
                exc,
            )
            self._identity_rejected = True
        self._set_available(False, exc)

    def _update_firmware_version(self, state: LockState) -> None:
        """Store the reported firmware version on the device entry, once."""
        if self._fw_version_set or not state.firmware_info:
            return

        # The lock reports the version prefixed, e.g. "FW:  1.2.3"; fall back to
        # the raw string if the prefix is missing.
        fw_version = (
            state.firmware_info.removeprefix("FW:").strip()
            or state.firmware_info.strip()
        )
        dev_reg = dr.async_get(self.hass)
        if not (
            device := dev_reg.async_get_device_by_identifier(
                (DOMAIN, cast(str, self._entry.unique_id)), self._entry.entry_id
            )
        ):
            _LOGGER.debug("No device entry found, cannot store firmware version")
            return

        dev_reg.async_update_device(device.id, sw_version=fw_version)
        self._fw_version_set = True

    @callback
    def _async_schedule_initial_read(self) -> None:
        """Read the lock once, the first time a scanner has actually seen it.

        The capability flags and firmware version only come over a connection,
        and connecting before the lock has advertised cannot work. Runs off the
        first advertisement instead, and retries on a later one if it fails.
        """
        # Checking done() rather than None: eagerly started tasks can finish
        # before the assignment below, which would leave a completed task here
        # forever and skip every retry.
        if (
            not self._probe_is_due()
            # A rejected identity does not recover on its own, so retrying only
            # wakes the lock on every advertisement for a read that cannot work.
            or self._identity_rejected
            or (self._initial_read is not None and not self._initial_read.done())
        ):
            return

        self._initial_read = self.hass.async_create_task(self._async_probe())

    def _probe_is_due(self) -> bool:
        """Return whether the capability read should run.

        Once for every lock, and then only again for one that reported it has
        no door status: Door Status Advice can be enabled in the Argo app at
        any time and shows up nowhere but a read, so a single "no" would leave
        the entity assuming state for good. Rate-limited, because each read
        wakes the lock. A lock that does report door status has nothing left
        to learn and is followed passively from here on.
        """
        if not self._probed:
            return True
        if self._door_status_supported is not False:
            return False
        return (
            self._last_probe is None
            or dt_util.utcnow() - self._last_probe >= _CAPABILITY_RECHECK
        )

    async def _async_probe(self) -> None:
        """Read the lock once, without letting a failure escape the task.

        _poll_state translates the errors it expects, but the client can raise
        others — a malformed handshake, for one — and an exception here would
        surface as an unretrieved task exception rather than a retry.
        """
        try:
            await self._poll_state(probing=True)
        except Exception:
            _LOGGER.debug("Probing the lock failed; will retry", exc_info=True)
        finally:
            # Stamped even on failure: a failed probe leaves _probed False and
            # retries on the next advertisement regardless, so this only ever
            # paces the recheck of a lock that already answered.
            self._last_probe = dt_util.utcnow()

    def _cancel_initial_read(self) -> None:
        """Cancel a pending first read."""
        if self._initial_read is not None and not self._initial_read.done():
            self._initial_read.cancel()

    def _async_get_ble_device(self) -> BLEDevice | None:
        """Return a device to connect to, falling back to the last advertised one.

        Clearing the manager's advertisement history to keep passive callbacks
        flowing also drops its device cache, so the lookup can come back empty
        for a lock that is plainly right there and advertising.
        """
        from_manager = async_ble_device_from_address(
            self.hass, self._entry.data[CONF_ADDRESS], connectable=True
        )
        _LOGGER.debug(
            "BLE device lookup: manager=%s cached=%s",
            from_manager,
            self._last_ble_device,
        )
        return from_manager or self._last_ble_device

    async def _poll_state(self, *, probing: bool = False) -> None:
        """Read door state via TLV_INFO and update HA state.

        ``probing`` marks a capability read — the one off the first
        advertisement, and the rare recheck after it. That advertisement has
        just proved the lock is there, so a transient failure to connect says
        nothing about reachability and must not override the availability it
        established: the read is retried on a later advertisement, and silence
        is what _check_availability is for. It also reads a lock that reported
        no door status, which the poll cycle otherwise leaves alone.
        """
        _LOGGER.debug("Polling lock state, current available: %s", self._attr_available)
        if self._ble_lock.locked():
            _LOGGER.debug("Skipping poll cycle — BLE operation already in progress")
            return

        if not (ble_device := self._async_get_ble_device()):
            if not probing:
                self._set_available(False, "device not found")
            return

        if (
            self._door_status_supported is False
            and not probing
            and not self._entry.options.get(CONF_ENABLE_POLLING, False)
        ):
            # Nothing to read from this lock: seeing it advertise is all the
            # reachability information there is, and it spares the battery a
            # connection on every poll cycle. With polling explicitly turned on,
            # keep reading — Door Status Advice can be enabled on the lock from
            # the Argo app at any time, and that only shows up in a read.
            self._set_available(True)
            return

        try:
            async with self._ble_lock:
                self.client.update_ble_device(ble_device)
                state: LockState = await self.client.read_state()
        except IseoAuthError as exc:
            self._reject_identity(exc)
            return
        except (TimeoutError, IseoConnectionError, OSError) as exc:
            if probing:
                _LOGGER.debug("Probing the lock failed; will retry: %s", exc)
                return
            self._set_available(False, exc)
            return

        self._probed = True
        self._identity_rejected = False
        self._set_available(True)
        self._update_firmware_version(state)

        if state.door_closed is None:
            _LOGGER.debug("Door status not supported, door polling disabled")
            self._door_status_supported = False
            # Without door status the state can only ever be assumed: the lock
            # re-latches on its own after every unlock.
            self._attr_assumed_state = True
            self._attr_is_locked = True
            self.async_write_ha_state()
            return

        self._door_status_supported = True
        self._attr_assumed_state = False

        self._apply_door_state(state.door_closed)

    def _set_unlocking(self, available: bool = True) -> None:
        self._attr_is_locked = False
        self._attr_is_unlocking = True
        self._attr_available = available
        self.async_write_ha_state()

    def _set_unlocked(self, available: bool = True) -> None:
        self._attr_is_unlocking = False
        self._attr_is_locked = False
        self._attr_available = available
        self._poll_suppress_until = dt_util.utcnow() + timedelta(seconds=_RELOCK_DELAY)
        self.async_write_ha_state()

    def _set_locked(self, available: bool = True) -> None:
        self._attr_is_unlocking = False
        self._attr_is_locked = True
        self._attr_available = available
        self._poll_suppress_until = None
        self.async_write_ha_state()

    async def _auto_relock(self) -> None:
        """Revert to 'locked' after the motor has re-latched.

        No read is needed to confirm it: once the suppression window closes the
        next advertisement carries the real door state and corrects this if the
        door was actually left open.
        """
        await asyncio.sleep(_RELOCK_DELAY)
        if self._door_seen_open:
            # The door is standing open as far as the last reading goes; leave
            # it that way until an advertisement reports it closed again.
            return
        self._set_locked(available=self._attr_available)

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

        # _door_seen_open is deliberately left alone: unlocking again while the
        # door already stands open must not discard that, or the relock timer
        # would report locked five seconds later. Only a closed reading clears
        # it.
        self._set_unlocking()

        if not (ble_device := self._async_get_ble_device()):
            self._set_locked(available=False)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            )

        try:
            async with self._ble_lock:
                self.client.update_ble_device(ble_device)
                await self.client.gw_open(remote_user_name="Home Assistant")
        except IseoAuthError as exc:
            # Same permanent rejection _poll_state() reports: keep the entity
            # unavailable rather than restoring it, so the opt-in poll timer
            # stops waking the lock with credentials that cannot work.
            self._set_locked(available=False)
            self._reject_identity(exc)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="lock_rejected_identity",
            ) from exc
        except (TimeoutError, IseoConnectionError, OSError) as exc:
            self._set_locked(available=False)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from exc

        self._identity_rejected = False
        self._set_unlocked()
        self._relock_task = self.hass.async_create_task(self._auto_relock())
