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
    parse_iseo_advertisement,
)

from homeassistant.components.bluetooth import (
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
    async_register_callback,
    async_track_unavailable,
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

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to advertisements and read the lock once for its firmware."""
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
            async_track_unavailable(
                self.hass, self._async_device_unavailable, address, connectable=False
            )
        )
        self.async_on_remove(self._cancel_relock_task)

        # A single read on setup, for the firmware version and an initial state
        # before the first advertisement lands. This is a one-off, not a timer.
        await self._poll_state()

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
        self._set_available(True)

        if self._door_status_supported is False:
            # The lock reported it does not support door status. Advertisements
            # carry no capability flags, so the door bit in them is meaningless
            # here — hearing the lock is all this tells us.
            return

        state = parse_iseo_advertisement(list(service_info.service_uuids or []))
        if state is None or state.door_closed is None:
            return

        self._door_status_supported = True
        self._attr_assumed_state = False

        if self._attr_is_unlocking:
            return
        if self._poll_suppress_until and dt_util.utcnow() < self._poll_suppress_until:
            return

        self._attr_is_locked = state.door_closed
        self.async_write_ha_state()

    @callback
    def _async_device_unavailable(
        self, _service_info: BluetoothServiceInfoBleak
    ) -> None:
        """Handle the lock no longer being seen by the bluetooth stack."""
        self._set_available(False, "no advertisement received")

    def _cancel_relock_task(self) -> None:
        """Cancel any pending relock task."""
        if self._relock_task and not self._relock_task.done():
            self._relock_task.cancel()

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

    async def _poll_state(self) -> None:
        """Read door state via TLV_INFO and update HA state."""
        _LOGGER.debug("Polling lock state, current available: %s", self._attr_available)
        if self._ble_lock.locked():
            _LOGGER.debug("Skipping poll cycle — BLE operation already in progress")
            return

        if not (
            ble_device := async_ble_device_from_address(
                self.hass,
                self._entry.data[CONF_ADDRESS],
                connectable=True,
            )
        ):
            self._set_available(False, "device not found")
            return

        if self._door_status_supported is False:
            # Nothing to read from this lock: seeing it advertise is all the
            # reachability information there is, and it spares the battery a
            # connection on every poll cycle.
            self._set_available(True)
            return

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
            return
        except (TimeoutError, IseoConnectionError, OSError) as exc:
            self._set_available(False, exc)
            return

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
