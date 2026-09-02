"""ISEO BLE Lock entity."""

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any, cast, override

from iseo_argo_ble import (
    IseoAuthError,
    IseoClient,
    IseoConnectionError,
    LockState,
    LogEntry,
    describe_event,
)

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.components.lock import LockEntity
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_platform
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.util import dt as dt_util

from . import IseoConfigEntry
from .const import DOMAIN, signal_access_log
from .event import EVENT_TYPE_ACCESS_DENIED, EVENT_TYPE_FAULT, EVENT_TYPE_OPENED

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

# Seconds the entity stays in "unlocked" state before reverting to "locked".
_RELOCK_DELAY = 5

# Seconds to wait after an unlock before re-polling the door state.
_RELOCK_POLL_DELAY = 2

# How often to poll the lock for door state (when door status is supported).
_POLL_INTERVAL = timedelta(seconds=30)

# Trailing debounce for the access log read. An unlock followed by the poll
# that notices the door is open would otherwise read the log twice.
_ACCESS_LOG_DEBOUNCE = 5

SERVICE_READ_ACCESS_LOG = "read_access_log"

# Access log event codes, grouped into the event types the log reports. Codes
# outside these groups (door closed, mode changes, enrolments) are read and
# discarded — they are not access events. See the library's event code table.
_OPEN_EVENT_CODES = frozenset({7, 8, 32, 33, 34, 45, 75, 102, 103})
_ACCESS_DENIED_EVENT_CODES = frozenset({5, 44, 52, 53, 68, 77, 86, 88, 89, 99})
_FAULT_EVENT_CODES = frozenset({21, 61, 90})

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
    async_add_entities([IseoLockEntity(entry)])
    entity_platform.async_get_current_platform().async_register_entity_service(
        SERVICE_READ_ACCESS_LOG, None, "async_read_access_log"
    )


class IseoLockEntity(LockEntity):
    """Represents an ISEO X1R BLE door lock.

    The X1R is a momentary latch release: it re-latches by itself a couple of
    seconds after being opened, so there is no way to lock it on demand and
    `async_lock` always raises. `unlock` (rather than `LockEntityFeature.OPEN`)
    is used for the release because the lock stays engaged in the door frame
    and the physical door itself is never operated.
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
        self._access_log_unsub: CALLBACK_TYPE | None = None
        self._access_log_task: asyncio.Task[None] | None = None
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

    @override
    async def async_added_to_hass(self) -> None:
        """Probe door-status support and start polling."""
        await self._poll_state()
        self.async_on_remove(
            async_track_time_interval(
                self.hass, self._async_poll_interval, _POLL_INTERVAL
            )
        )
        self.async_on_remove(self._cancel_relock_task)
        self.async_on_remove(self._cancel_access_log_read)

    async def _async_poll_interval(self, _now: datetime) -> None:
        """Poll the lock on the configured interval."""
        await self._poll_state()

    def _cancel_relock_task(self) -> None:
        """Cancel any pending relock task."""
        if self._relock_task and not self._relock_task.done():
            self._relock_task.cancel()

    def _cancel_access_log_read(self) -> None:
        """Cancel a pending or running access log read."""
        if self._access_log_unsub is not None:
            self._access_log_unsub()
            self._access_log_unsub = None
        if self._access_log_task and not self._access_log_task.done():
            self._access_log_task.cancel()

    def _set_available(self, available: bool, reason: object = None) -> None:
        """Update availability, logging only when it actually changes."""
        if self._attr_available == available:
            return
        if available:
            _LOGGER.info("Lock is back online")
        else:
            _LOGGER.info("Lock is unavailable: %s", reason)
        self._attr_available = available
        self.async_write_ha_state()

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

    async def _poll_state(self, force: bool = False) -> bool:
        """Read door state via TLV_INFO and update HA state.

        Returns True when a fresh door reading was applied to the entity.
        """
        _LOGGER.debug("Polling lock state, current available: %s", self._attr_available)
        if self._ble_lock.locked():
            _LOGGER.debug("Skipping poll cycle — BLE operation already in progress")
            return False

        if not (
            ble_device := async_ble_device_from_address(
                self.hass,
                self._entry.data[CONF_ADDRESS],
                connectable=True,
            )
        ):
            self._set_available(False, "device not found")
            return False

        if self._door_status_supported is False:
            # Nothing to read from this lock: seeing it advertise is all the
            # reachability information there is, and it spares the battery a
            # connection on every poll cycle.
            self._set_available(True)
            return False

        try:
            async with self._ble_lock:
                self.client.update_ble_device(ble_device)
                state: LockState = await self.client.read_state()
        except IseoAuthError as exc:
            if self._attr_available:
                # Rejected credentials do not recover on their own: the gateway
                # identity has to be enrolled on the lock again.
                _LOGGER.warning(
                    "Lock rejected the Home Assistant identity (%s), delete the "
                    "integration and set it up again to enroll it anew",
                    exc,
                )
                self._attr_available = False
                self.async_write_ha_state()
            return False
        except (TimeoutError, IseoConnectionError, OSError) as exc:
            self._set_available(False, exc)
            return False

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
            return False

        self._door_status_supported = True

        if self._attr_is_unlocking:
            return False
        if (
            not force
            and self._poll_suppress_until
            and dt_util.utcnow() < self._poll_suppress_until
        ):
            return False

        # `is_locked` is None until the first reading, so the first poll of a
        # standing-open door is not mistaken for someone opening it.
        door_opened = bool(self._attr_is_locked) and not state.door_closed
        self._attr_is_locked = state.door_closed
        self.async_write_ha_state()
        if door_opened:
            self._schedule_access_log_read()
        return True

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
        """Revert to 'locked' after the motor has re-latched."""
        if self._door_status_supported:
            await asyncio.sleep(_RELOCK_POLL_DELAY)
            if not await self._poll_state(force=True):
                # The poll took no reading (BLE busy, device not found, error),
                # so fall back to the lock's own re-latching behaviour.
                self._set_locked(available=self._attr_available)
            return

        await asyncio.sleep(_RELOCK_DELAY)
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
        """Debounce elapsed — read the log, unless a read is already running."""
        self._access_log_unsub = None
        if self._access_log_task and not self._access_log_task.done():
            return
        self._access_log_task = self.hass.async_create_task(self._async_read_log())

    async def async_read_access_log(self) -> None:
        """Read the lock's unread access log now.

        The same read the lock does after a door open, on demand: useful to
        pick up entries recorded while the door state was not being watched.
        """
        if self._access_log_unsub is not None:
            self._access_log_unsub()
            self._access_log_unsub = None
        if not async_ble_device_from_address(
            self.hass, self._entry.data[CONF_ADDRESS], connectable=True
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            )
        await self._async_read_log()

    async def _async_read_log(self) -> None:
        """Drain the unread access log and report what it holds.

        Reading is destructive — the lock marks the entries read — so every
        entry is only ever seen once, by whichever read gets there first.
        """
        if not (
            ble_device := async_ble_device_from_address(
                self.hass, self._entry.data[CONF_ADDRESS], connectable=True
            )
        ):
            _LOGGER.debug("No BLE device available to read the access log")
            return

        try:
            async with self._ble_lock:
                self.client.update_ble_device(ble_device)
                entries = await self.client.gw_read_unread_logs()
        except (TimeoutError, IseoConnectionError, IseoAuthError, OSError) as exc:
            _LOGGER.debug("Could not read the access log: %s", exc)
            return

        self._report_log_entries(entries)

    @callback
    def _report_log_entries(self, entries: list[LogEntry]) -> None:
        """Report the newest entry of each kind, oldest first.

        A read can return a long backlog — every open since the last one, plus
        closes and mode changes. Reporting all of it would replay history as if
        it had just happened, so only the newest of each kind is reported, in
        timestamp order so the entity ends up on the most recent one.
        """
        newest: list[tuple[str, LogEntry]] = []
        for event_type, codes in _EVENT_TYPE_CODES:
            matching = [entry for entry in entries if entry.event_code in codes]
            if matching:
                newest.append(
                    (event_type, max(matching, key=lambda entry: entry.timestamp))
                )

        for event_type, entry in sorted(newest, key=lambda item: item[1].timestamp):
            _LOGGER.debug(
                "Access log: %s (code %s) at %s",
                describe_event(entry.event_code),
                entry.event_code,
                entry.timestamp,
            )
            async_dispatcher_send(
                self.hass,
                signal_access_log(self._entry.entry_id),
                event_type,
                {
                    "event_code": entry.event_code,
                    "description": describe_event(entry.event_code),
                    # The lock records the opener across two free-form fields;
                    # which one carries a readable name depends on the
                    # credential, so prefer the description and fall back.
                    "opened_by": entry.extra_description.strip()
                    or entry.user_info.strip()
                    or None,
                    "occurred_at": entry.timestamp.isoformat(),
                },
            )

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

        self._set_unlocking()

        if not (
            ble_device := async_ble_device_from_address(
                self.hass,
                self._entry.data[CONF_ADDRESS],
                connectable=True,
            )
        ):
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
            self._set_locked()
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

        self._set_unlocked()
        self._relock_task = self.hass.async_create_task(self._auto_relock())
        # An unlock from Home Assistant marks the entity unlocked before the
        # poll ever sees the door move, so it never looks like a door open —
        # read the log directly to report who pressed the button.
        self._schedule_access_log_read()
