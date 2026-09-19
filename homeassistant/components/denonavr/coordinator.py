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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import ACTION_REFRESH_DEBOUNCE_COOLDOWN, DOMAIN

_LOGGER = logging.getLogger(__name__)

# Matches media_player.py's own existing exception categorization: these
# indicate the receiver itself is unreachable or misbehaving, and should
# mark it unavailable. Other DenonAvrError subclasses (e.g.
# AvrCommandError, a rejected/invalid single command) don't - they're
# not a connectivity problem, just logged and otherwise ignored.
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

    Doesn't hold meaningful `.data` itself - entities read live
    properties directly off the shared `receiver` object, the same way
    they always have. This coordinator's job is purely to own *when*
    that object gets refreshed, and to notify every entity that cares
    when it has been.
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

        The lock is passed in rather than derived from the receiver:
        denonavr's attrs classes are unhashable, so they can't be
        dict/weak-ref keys.
        """
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{DOMAIN}_{name}",
            config_entry=config_entry,
            update_interval=update_interval,
            # immediate=False: the receiver needs a moment to settle
            # before a post-action confirm reads back the right value,
            # and this coalesces near-simultaneous actions into one refresh.
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

    async def async_refresh_forced(self) -> None:
        """Refresh immediately, bypassing the Telnet-healthy skip.

        For explicit on-demand refreshes (e.g. the update_audyssey
        media player action) where the caller needs a confirmed fresh
        read even though Telnet already looks healthy - regular
        polling and post-action confirmations still go through
        async_refresh()/async_request_refresh(), which keep that skip.

        Serialized on its own lock: async_refresh() waits on the
        debouncer lock only after the flag is set, so overlapping
        callers would clear it for each other and the later refresh
        would silently run unforced. Acquired before the debouncer and
        receiver locks, never after, so it adds no deadlock path.
        """
        async with self._force_refresh_lock:
            self._force_next_refresh = True
            try:
                await self.async_refresh()
            finally:
                self._force_next_refresh = False

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

    For use outside the coordinator's own refresh cycle - e.g. an
    entity's or media_player.py's own command failing with a
    connectivity-type error - so availability reflects that
    immediately rather than waiting for the next scheduled poll.
    """
    if coordinator.last_update_success:
        coordinator.last_update_success = False
        coordinator.async_update_listeners()
