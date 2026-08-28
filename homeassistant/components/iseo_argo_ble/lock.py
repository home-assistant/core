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

# How long to wait for an advertisement to make the lock reachable again before
# connecting anyway and letting the retry logic take over.
_ADVERTISEMENT_WAIT = 30
_AVAILABILITY_CHECK_INTERVAL = timedelta(minutes=1)


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

    Door state comes from the lock's advertisements, which the lock already
    broadcasts: following those reports changes as they happen instead of up to
    30 seconds later, and spares the lock a connection and its battery a wake-up
    every cycle. Connecting on a timer remains available for locks that cannot
    report door status passively.
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
        self._advertised = asyncio.Event()
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
        self.async_on_remove(self._cancel_relock_task)

        if self._entry.options.get(CONF_ENABLE_POLLING, False):
            self.async_on_remove(
                async_track_time_interval(
                    self.hass, self._async_poll_interval, _POLL_INTERVAL
                )
            )

    async def _async_poll_interval(self, _now: datetime) -> None:
        """Poll the lock on the configured interval."""
        await self._poll_state()

    @callback
    def _async_handle_advertisement(
        self, service_info: BluetoothServiceInfoBleak, _change: BluetoothChange
    ) -> None:
        """Apply the door state the lock encodes in its advertisement."""
        self._last_advertisement = dt_util.utcnow()
        self._last_ble_device = service_info.device
        self._advertised.set()
        self._set_available(True)
        self._async_schedule_initial_read()

        # The lock encodes door state in the set of service UUIDs it advertises
        # rather than in changing payload bytes, so without resetting the
        # scanners' merge state the entity would never see the door close again.
        #
        # That same state is what the scanners hand out as their discovered
        # device, so clearing it makes the lock unreachable until it advertises
        # again. Leave it alone while a connection is being made, or the
        # connection can never resolve a backend to reach it through.
        if not self._ble_lock.locked():
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

        if self._attr_is_unlocking:
            return
        if self._poll_suppress_until and dt_util.utcnow() < self._poll_suppress_until:
            return

        self._attr_is_locked = state.door_closed
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

    async def _async_wait_until_reachable(self) -> None:
        """Wait for an advertisement to put the lock back in a scanner's records.

        Resetting the scanners' merge state to keep door updates flowing also
        drops their record of the device, so a connection started just after an
        advertisement has no path to route through and burns its retries. Call
        this with _ble_lock held: that suppresses further clearing, so the next
        advertisement sticks and the connection goes straight through.
        """
        address = self._entry.data[CONF_ADDRESS]
        if async_ble_device_from_address(self.hass, address, connectable=True):
            return

        _LOGGER.debug("Waiting for an advertisement before connecting")
        self._advertised.clear()
        try:
            async with asyncio.timeout(_ADVERTISEMENT_WAIT):
                await self._advertised.wait()
        except TimeoutError:
            _LOGGER.debug(
                "No advertisement in %ss, connecting anyway", _ADVERTISEMENT_WAIT
            )

    @callback
    def _async_schedule_initial_read(self) -> None:
        """Read the lock once, the first time a scanner has actually seen it.

        The capability flags and firmware version only come over a connection,
        and connecting before the lock has advertised cannot work. Runs off the
        first advertisement instead, and retries on a later one if it fails.
        """
        if self._initial_read is not None or self._door_status_supported is not None:
            return

        async def _read() -> None:
            try:
                await self._poll_state()
            finally:
                self._initial_read = None

        self._initial_read = self.hass.async_create_task(_read())
        self.async_on_remove(self._cancel_initial_read)

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

    async def _poll_state(self) -> None:
        """Read door state via TLV_INFO and update HA state."""
        _LOGGER.debug("Polling lock state, current available: %s", self._attr_available)
        if self._ble_lock.locked():
            _LOGGER.debug("Skipping poll cycle — BLE operation already in progress")
            return

        if not (ble_device := self._async_get_ble_device()):
            self._set_available(False, "device not found")
            return

        if self._door_status_supported is False and not self._entry.options.get(
            CONF_ENABLE_POLLING, False
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
                await self._async_wait_until_reachable()
                self.client.update_ble_device(ble_device)
                state: LockState = await self.client.read_state()
        except IseoAuthError as exc:
            if not self._identity_rejected:
                # Rejected credentials do not recover on their own: the gateway
                # identity has to be enrolled on the lock again.
                _LOGGER.warning(
                    "Lock rejected the Home Assistant identity (%s), delete the "
                    "integration and set it up again to enroll it anew",
                    exc,
                )
                self._identity_rejected = True
                self._attr_available = False
                self.async_write_ha_state()
            return
        except (TimeoutError, IseoConnectionError, OSError) as exc:
            self._set_available(False, exc)
            return

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

        if self._attr_is_unlocking:
            return
        if self._poll_suppress_until and dt_util.utcnow() < self._poll_suppress_until:
            return

        self._attr_is_locked = state.door_closed
        self.async_write_ha_state()

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

        self._set_unlocking()

        if not (ble_device := self._async_get_ble_device()):
            self._set_locked(available=False)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            )

        try:
            async with self._ble_lock:
                await self._async_wait_until_reachable()
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

        self._identity_rejected = False
        self._set_unlocked()
        self._relock_task = self.hass.async_create_task(self._auto_relock())
