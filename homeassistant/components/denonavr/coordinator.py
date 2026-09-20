"""DataUpdateCoordinators for Denon AVR.

Separate coordinators handle general status and Audyssey data: a
single coordinator can't have one interval that's both always-on and
opt-in, which "Update Audyssey settings" requires.
"""

import asyncio
from datetime import timedelta
import logging
from typing import Protocol, override

from denonavr import DenonAVR
from denonavr.exceptions import (
    AvrForbiddenError,
    AvrIncompleteResponseError,
    AvrInvalidResponseError,
    AvrNetworkError,
    AvrTimoutError,
    DenonAvrError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import ACTION_REFRESH_DEBOUNCE_COOLDOWN, DOMAIN

_LOGGER = logging.getLogger(__name__)

# Errors that mean the receiver itself is unreachable or misbehaving, so it
# is marked unavailable. Every other DenonAvrError is a single rejected
# command, which is logged and otherwise ignored.
UNAVAILABLE_ON = (
    AvrTimoutError,
    AvrNetworkError,
    AvrForbiddenError,
    AvrInvalidResponseError,
    AvrIncompleteResponseError,
)


async def async_refresh_status(receiver: DenonAVR, *, force: bool = False) -> None:
    """Refresh general receiver status for every configured zone.

    Skips the HTTP poll if Telnet is already healthy and keeping
    everything current - that connection state is shared across zones
    (it lives on the underlying device, not per zone), so it only
    needs checking once regardless of how many zones are enabled.
    force=True bypasses this, for callers that need a confirmed fresh
    read regardless (see DenonAvrDataUpdateCoordinator.async_refresh_forced).

    A non-connectivity error in one zone doesn't stop the others from
    refreshing - only genuine connectivity errors do (re-raised so the
    caller can still fail the whole update for those, same as before).
    """
    if not force and receiver.telnet_connected and receiver.telnet_healthy:
        return
    for zone_receiver in receiver.zones.values():
        try:
            await zone_receiver.async_update()
        except UNAVAILABLE_ON:
            raise
        except DenonAvrError as err:
            _LOGGER.debug(
                "Error refreshing zone %s for %s: %s",
                zone_receiver.zone,
                receiver.name,
                err,
            )


async def async_refresh_audyssey(receiver: DenonAVR, *, force: bool = False) -> None:
    """Refresh Audyssey settings for every configured zone.

    Each zone is its own object with its own cached Audyssey state
    (denonavr's async_update_audyssey() only updates the zone it's
    called on), so Zone2/Zone3 media players need their own fetch too -
    matching receiver.py's Telnet-setup fetch and async_refresh_status's
    own per-zone loop.

    Skips the HTTP poll if Telnet is already healthy and keeping
    everything current, for the same reason and in the same
    all-zones-at-once way as async_refresh_status's matching guard -
    unless force=True: Telnet only pushes Audyssey data on a change,
    never on connect, so the one-time initial fetch needs to bypass
    this or these entities could start unavailable and stay that way
    indefinitely.
    """
    if not force and receiver.telnet_connected and receiver.telnet_healthy:
        return
    for zone_receiver in receiver.zones.values():
        try:
            await zone_receiver.async_update_audyssey()
        except UNAVAILABLE_ON:
            raise
        except DenonAvrError as err:
            _LOGGER.debug(
                "Error refreshing Audyssey for zone %s for %s: %s",
                zone_receiver.zone,
                receiver.name,
                err,
            )


class _RefreshFn(Protocol):
    """Callback signature shared by async_refresh_status/async_refresh_audyssey."""

    async def __call__(self, receiver: DenonAVR, *, force: bool = False) -> None: ...


class DenonAvrDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Coordinate one aspect of a Denon AVR receiver's state.

    Holds no `.data`: entities read live properties off the shared
    `receiver` object. This owns when that object is refreshed, and
    notifies the entities once it has been.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        receiver: DenonAVR,
        lock: asyncio.Lock,
        name: str,
        update_interval: timedelta | None,
        refresh_fn: _RefreshFn,
    ) -> None:
        """Initialize the coordinator with a shared receiver lock.

        The lock is passed in because denonavr's attrs classes are
        unhashable and cannot be dict or weak-ref keys.
        """
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{DOMAIN}_{name}",
            config_entry=config_entry,
            update_interval=update_interval,
            # immediate=False: the receiver needs a moment to settle before a
            # confirming read, and it coalesces near-simultaneous actions.
            request_refresh_debouncer=Debouncer(
                hass,
                _LOGGER,
                cooldown=ACTION_REFRESH_DEBOUNCE_COOLDOWN,
                immediate=False,
            ),
        )
        self.receiver = receiver
        self.lock = lock
        self._refresh_fn = refresh_fn
        self._force_next_refresh = False
        self._force_refresh_lock = asyncio.Lock()
        self._forced_refresh_count = 0
        self._internal_listeners: list[CALLBACK_TYPE] = []

    @callback
    def async_add_internal_listener(
        self, update_callback: CALLBACK_TYPE
    ) -> CALLBACK_TYPE:
        """Register one of the integration's own callbacks for updates.

        async_add_listener() starts the update interval for its first
        listener, so wiring the coordinators to each other through it would
        keep polling even with every entity disabled.
        """
        self._internal_listeners.append(update_callback)

        @callback
        def _remove_listener() -> None:
            self._internal_listeners.remove(update_callback)

        return _remove_listener

    @callback
    @override
    def async_update_listeners(self) -> None:
        """Notify the entities, then the integration's own callbacks."""
        super().async_update_listeners()
        for update_callback in list(self._internal_listeners):
            update_callback()

    async def async_refresh_forced(self) -> None:
        """Refresh immediately, bypassing the Telnet-healthy skip.

        For on-demand refreshes that need a confirmed fresh read; regular
        polling and post-action confirmations keep the skip.

        Overlapping callers share the refresh that is already running
        instead of queueing another full read: settings changed together
        expire together, and each of these reads is an expensive round
        trip per zone. Sharing is sound because a pending value outlives
        a refresh by far, so one already running when the expiry fires
        still started after the command it has to confirm.

        The lock is its own rather than the receiver's: async_refresh()
        reaches the debouncer lock only after the flag is set, so
        overlapping callers would otherwise clear it for each other and
        the later refresh would run unforced. Taken before the debouncer
        and receiver locks, never after.
        """
        joined = self._forced_refresh_count
        async with self._force_refresh_lock:
            if self._forced_refresh_count != joined:
                return
            self._force_next_refresh = True
            try:
                await self.async_refresh()
            finally:
                self._force_next_refresh = False
                self._forced_refresh_count += 1

    @override
    async def _async_update_data(self) -> None:
        """Refresh the receiver via this coordinator's refresh_fn."""
        async with self.lock:
            try:
                await self._refresh_fn(self.receiver, force=self._force_next_refresh)
            except UNAVAILABLE_ON as err:
                raise UpdateFailed(
                    f"Error communicating with {self.receiver.name}: {err}"
                ) from err
            except DenonAvrError as err:
                _LOGGER.debug(
                    "Error refreshing %s for %s: %s",
                    self.name,
                    self.receiver.name,
                    err,
                )


@callback
def mark_unavailable(coordinator: DenonAvrDataUpdateCoordinator) -> None:
    """Mark a coordinator unavailable after a confirmed connectivity failure.

    For failures outside the refresh cycle, such as a command of an entity's
    own, so availability reflects them without waiting for the next poll.
    """
    if coordinator.last_update_success:
        coordinator.last_update_success = False
        coordinator.async_update_listeners()
