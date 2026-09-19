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
    LogEntry,
    describe_event,
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
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.util import dt as dt_util

from . import ACCESS_LOG_READS, PENDING_LOG_ENTRIES, IseoConfigEntry, async_get_ble_lock
from .const import CONF_ENABLE_POLLING, DOMAIN, signal_access_log
from .event import EVENT_TYPE_ACCESS_DENIED, EVENT_TYPE_FAULT, EVENT_TYPE_OPENED

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

# Trailing debounce for the access log read. An unlock followed by the
# advertisement that reports the door open would otherwise read the log twice.
_ACCESS_LOG_DEBOUNCE = 5

# Access log event codes, grouped into the event types the log reports. Codes
# outside these groups (door closed, mode changes, enrolments, power and
# Bluetooth lifecycle) are read and discarded — they are not access events.
# Reading the log destroys it on the lock, so anything left out here is gone
# for good; the groups below are meant to cover the whole event table's
# denials and faults, not a sample of them. See the library's event code table
# (`iseo_argo_ble.LOG_EVENT_DESCRIPTIONS`).
_OPEN_EVENT_CODES = frozenset({7, 8, 32, 33, 34, 45, 75, 102, 103})
# An attempt to open that the lock refused.
_ACCESS_DENIED_EVENT_CODES = frozenset(
    {3, 4, 5, 13, 31, 44, 51, 52, 53, 62, 68, 77, 86, 88, 89, 99}
)
# The lock could not do its job: it failed to drive the bolts, a peripheral
# misbehaved, or it is out of memory or battery.
_FAULT_EVENT_CODES = frozenset(
    {6, 21, 22, 23, 24, 25, 26, 27, 57, 61, 67, 70, 71, 90, 98, 106}
)

_EVENT_TYPE_CODES = (
    (EVENT_TYPE_OPENED, _OPEN_EVENT_CODES),
    (EVENT_TYPE_ACCESS_DENIED, _ACCESS_DENIED_EVENT_CODES),
    (EVENT_TYPE_FAULT, _FAULT_EVENT_CODES),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IseoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ISEO lock entity from a config entry."""
    async_add_entities(
        [IseoLockEntity(entry, async_get_ble_lock(hass, entry.entry_id))]
    )


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
        ble_lock: asyncio.Lock,
    ) -> None:
        """Initialize the lock entity.

        The BLE mutex is passed in rather than created here: the lock accepts
        a single connection at a time, and a destructive access-log read can
        outlive the entity that started it, so it has to keep excluding a
        replacement entity's polls and unlocks too.
        """
        self._entry = entry
        self._relock_task: asyncio.Task[None] | None = None
        self._ble_lock = ble_lock
        self._door_status_supported: bool | None = None
        self._fw_version_set = False
        self._access_log_unsub: CALLBACK_TYPE | None = None
        self._access_log_task: asyncio.Task[None] | None = None
        self.client: IseoClient = entry.runtime_data.client

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
        self.async_on_remove(self._cancel_access_log_read)

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

        # The lock records who opened the door in its own log, so an opening is
        # what makes a read worth spending. Hooked here rather than on the
        # advertisement, so a lock on the polling fallback reads its log too.
        # `is_locked` is None until the first reading, so a door already
        # standing open when Home Assistant starts is not mistaken for someone
        # opening it, and an unlock from Home Assistant — which marks the
        # entity unlocked before the door moves — reads the log on its own.
        door_opened = not door_closed and self._attr_is_locked is True

        self._door_seen_open = not door_closed
        self._attr_is_locked = door_closed
        self.async_write_ha_state()
        if door_opened:
            self._schedule_access_log_read()

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

    def _cancel_access_log_read(self) -> None:
        """Drop a read that has not started touching the lock yet.

        Only the debounce is cancelled. A read already in flight is left to
        finish: fetching a page marks those entries read on the lock, so
        cancelling between the drain and the report would lose them for good.
        """
        if self._access_log_unsub is not None:
            self._access_log_unsub()
            self._access_log_unsub = None

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

    @callback
    def _schedule_access_log_read(self) -> None:
        """(Re)arm the trailing debounce for the access log read.

        Restarting the timer means one read once the door has settled, rather
        than one per event: the read drains everything unread anyway.
        """
        if self._access_log_unsub is not None:
            self._access_log_unsub()
        self._access_log_unsub = async_call_later(
            self.hass, _ACCESS_LOG_DEBOUNCE, self._start_access_log_read
        )

    @callback
    def _start_access_log_read(self, _now: datetime) -> None:
        """Debounce elapsed — read the log in the background."""
        self._access_log_unsub = None
        if not self._entry.runtime_data.access_log_consumer:
            # Reading empties the lock's log. With the event entity disabled
            # there is nobody to report to, so the entries would be destroyed
            # and never seen.
            _LOGGER.debug("Access log entity is not enabled; skipping the read")
            return
        self.hass.async_create_task(self._async_background_read())

    def _async_shared_read(self) -> asyncio.Task[None]:
        """Return the read already running, or start one.

        Every caller joins the same read. Reading is destructive, so a second
        one would spend another BLE session to find the log already emptied by
        the first.

        The registry is consulted before this entity's own handle, because a
        read can outlive the entity that started it: unloading waits only a
        bounded time, so reloading an entry mid-read leaves the old read
        draining the lock while this replacement entity starts with no handle
        on it. Joining it is what keeps the "one destructive read at a time"
        rule true across a reload.
        """
        reads = self.hass.data.setdefault(ACCESS_LOG_READS, {})
        entry_id = self._entry.entry_id
        running = reads.get(entry_id)
        if running is not None and not running.done():
            self._access_log_task = running
            return running

        if self._access_log_task is None or self._access_log_task.done():
            # Unloading waits on this: the entries are already marked read on
            # the lock, so the event entity must still be listening when they
            # are reported.
            task = self.hass.async_create_task(self._async_read_log())
            self._access_log_task = task
            reads[entry_id] = task

            def _forget(done: asyncio.Task[None]) -> None:
                """Drop the finished read, unless a later one took its place."""
                if reads.get(entry_id) is done:
                    del reads[entry_id]

            task.add_done_callback(_forget)
        return self._access_log_task

    async def _async_join_read(self) -> None:
        """Wait for the shared read without being able to cancel it.

        Waiters shield their own await: a caller that goes away must not
        cancel the read itself. The lock marks entries read as each page is
        fetched, so cancelling one would lose them, and the tracked task would
        also look finished and let the next caller start a second BLE session
        over an already-emptied log.
        """
        await asyncio.shield(self._async_shared_read())

    async def _async_background_read(self) -> None:
        """Read the log without troubling anyone if it fails.

        Nothing is lost: a failed read leaves the entries on the lock, and the
        next read picks them up.
        """
        try:
            await self._async_join_read()
        except HomeAssistantError as err:
            _LOGGER.debug("Could not read the access log: %s", err)

    async def async_read_access_log(self) -> None:
        """Read the lock's unread access log now.

        The same read the lock does after a door open, on demand: useful to
        pick up entries recorded while the door state was not being watched.
        """
        if self._access_log_unsub is not None:
            self._access_log_unsub()
            self._access_log_unsub = None
        if not self._entry.runtime_data.access_log_consumer:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="access_log_entity_disabled",
            )
        await self._async_join_read()

    async def _async_read_log(self) -> None:
        """Drain the unread access log and report what it holds.

        Reading is destructive — the lock marks the entries read — so every
        entry is only ever seen once, by whichever read gets there first.
        """
        if not (ble_device := self._async_get_ble_device()):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="device_not_found",
                translation_placeholders={"address": self._entry.data[CONF_ADDRESS]},
            )

        try:
            await self._async_drain_and_report(ble_device)
        except IseoAuthError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="lock_rejected_identity",
            ) from err
        except (TimeoutError, IseoConnectionError, OSError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err

    async def _async_drain_and_report(self, ble_device: BLEDevice) -> None:
        """Read the unread entries and report them, without interruption."""
        async with self._ble_lock:
            self.client.update_ble_device(ble_device)
            entries = await self.client.gw_read_unread_logs()
        self._report_log_entries(entries)

    @callback
    def _report_log_entries(self, entries: list[LogEntry]) -> None:
        """Report the newest entry of each kind, oldest first.

        A read can return a long backlog — every open since the last one, plus
        closes and mode changes. Reporting all of it would replay history as if
        it had just happened, so only the newest of each kind is reported, in
        timestamp order so the entity ends up on the most recent one.
        """
        # Timestamps have one-second precision, so entries sharing a second
        # need the position the lock handed them over in as the tie-breaker:
        # the log is drained oldest first, so a later position is a later
        # event. Without it max() keeps the earliest of a tied group, and the
        # ordering below falls back to the order of _EVENT_TYPE_CODES, either
        # of which can leave an older event as the entity's final state.
        newest: list[tuple[int, str, LogEntry]] = []
        for event_type, codes in _EVENT_TYPE_CODES:
            matching = [
                (position, entry)
                for position, entry in enumerate(entries)
                if entry.event_code in codes
            ]
            if matching:
                position, entry = max(
                    matching, key=lambda item: (item[1].timestamp, item[0])
                )
                newest.append((position, event_type, entry))

        for _position, event_type, entry in sorted(
            newest, key=lambda item: (item[2].timestamp, item[0])
        ):
            _LOGGER.debug(
                "Access log: %s (code %s) at %s",
                describe_event(entry.event_code),
                entry.event_code,
                entry.timestamp,
            )
            attributes = {
                "event_code": entry.event_code,
                "description": describe_event(entry.event_code),
                # The lock puts the opener's name in extra_description and
                # their credential's UUID in user_info. Falling back to the
                # UUID would put a 32-character hex string where a name
                # belongs, so the two are reported separately.
                "opened_by": entry.extra_description.strip() or None,
                "credential_id": entry.user_info.strip() or None,
                "occurred_at": entry.timestamp.isoformat(),
            }
            # runtime_data is deleted once the entry has unloaded, which is
            # precisely when the buffer below is needed, so this cannot assume
            # it is still there.
            data = getattr(self._entry, "runtime_data", None)
            if data is not None and data.access_log_consumer:
                async_dispatcher_send(
                    self.hass,
                    signal_access_log(self._entry.entry_id),
                    event_type,
                    attributes,
                )
            else:
                # The entity went away while the lock was being drained. These
                # entries are already marked read there, so hold them until it
                # comes back rather than dropping them.
                self.hass.data.setdefault(PENDING_LOG_ENTRIES, {}).setdefault(
                    self._entry.entry_id, []
                ).append((event_type, attributes))

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
        # An unlock from Home Assistant marks the entity unlocked before the
        # poll ever sees the door move, so it never looks like a door open —
        # read the log directly to report who pressed the button.
        self._schedule_access_log_read()
