"""DataUpdateCoordinators for Denon AVR.

Separate coordinators handle general status and Audyssey data: the slow
Audyssey query polls only with "Update Audyssey settings" on, but must
still be refreshable on demand without joining every status refresh.
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

# The receiver is unreachable or misbehaving, so mark it unavailable. Every
# other DenonAvrError is one rejected command: logged, otherwise ignored.
UNAVAILABLE_ON = (
    AvrTimoutError,
    AvrNetworkError,
    AvrForbiddenError,
    AvrInvalidResponseError,
    AvrIncompleteResponseError,
)


async def async_refresh_status(receiver: DenonAVR, *, force: bool = False) -> None:
    """Refresh general receiver status for every configured zone.

    Skipped while Telnet is healthy; that state lives on the device, not per
    zone. force=True bypasses the skip. Only connectivity errors abort the
    remaining zones, and they re-raise to fail the whole update.
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


async def async_update_zone_audyssey(zone_receiver: DenonAVR) -> None:
    """Read one zone's Audyssey settings.

    A receiver without Audyssey answers the query short, which is a missing
    feature rather than an unreachable receiver.
    """
    try:
        await zone_receiver.async_update_audyssey()
    except AvrIncompleteResponseError as err:
        _LOGGER.debug(
            "No Audyssey data for zone %s for %s: %s",
            zone_receiver.zone,
            zone_receiver.name,
            err,
        )


async def async_refresh_audyssey(receiver: DenonAVR, *, force: bool = False) -> None:
    """Refresh Audyssey settings for every configured zone.

    async_update_audyssey() only updates the zone it is called on, so Zone2
    and Zone3 need their own fetch. Skipped while Telnet is healthy unless
    force=True: Telnet never pushes on connect, and unlike status, which
    receiver.py reads before connecting, nothing else fetches this at setup.
    """
    if not force and receiver.telnet_connected and receiver.telnet_healthy:
        return
    for zone_receiver in receiver.zones.values():
        try:
            await async_update_zone_audyssey(zone_receiver)
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
    """Callback signature shared by async_refresh_status/async_refresh_audyssey.

    Raises only UNAVAILABLE_ON; any other DenonAvrError is handled per zone.
    """

    async def __call__(self, receiver: DenonAVR, *, force: bool = False) -> None: ...


class DenonAvrDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Coordinate one aspect of a Denon AVR receiver's state.

    Holds no `.data`: entities read live properties off the shared
    `receiver` object. This owns when that object is refreshed, and
    notifies the entities once it has been.
    """

    config_entry: ConfigEntry

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
        # The other coordinator on the same receiver, set once both exist.
        self.peer: DenonAvrDataUpdateCoordinator | None = None
        self._force_refresh_lock = asyncio.Lock()
        self._forced_refresh_count = 0
        self._internal_listeners: list[CALLBACK_TYPE] = []

    @property
    def polls(self) -> bool:
        """Whether this coordinator's own poll settles its availability.

        A poll reads rather than skips while either coordinator is failed, so
        it finds a failure or confirms a recovery within one interval. Without
        a recurring poll, or with polling disabled for the entry, the other
        coordinator has to hand it the verdict.
        """
        return (
            self.update_interval is not None
            and not self.config_entry.pref_disable_polling
        )

    @callback
    def async_add_internal_listener(
        self, update_callback: CALLBACK_TYPE
    ) -> CALLBACK_TYPE:
        """Register one of the integration's own callbacks for updates.

        Not async_add_listener(): that starts the update interval for its
        first listener, which would poll with every entity disabled.

        Runs on every refresh attempt and every out-of-band failure, so one
        refresh can run it twice: callbacks must be idempotent.
        """
        self._internal_listeners.append(update_callback)

        @callback
        def _remove_listener() -> None:
            self._internal_listeners.remove(update_callback)

        return _remove_listener

    @callback
    def _async_notify_internal_listeners(self) -> None:
        """Run the integration's own callbacks."""
        for update_callback in list(self._internal_listeners):
            update_callback()

    @callback
    @override
    def _async_refresh_finished(self) -> None:
        """Run the integration's own callbacks after every refresh attempt.

        The base class stops notifying listeners once a failure repeats, which
        would leave the other coordinator available if it had recovered in
        between two of these failures.
        """
        self._async_notify_internal_listeners()

    @callback
    @override
    def async_update_listeners(self) -> None:
        """Notify the entities, then the integration's own callbacks."""
        super().async_update_listeners()
        self._async_notify_internal_listeners()

    async def async_refresh_forced(self) -> None:
        """Refresh immediately, bypassing the Telnet-healthy skip.

        Overlapping callers join the refresh in flight. Its own lock, not the
        receiver's: async_refresh() reaches the debouncer lock only after the
        bypass flag is set, so concurrent callers would clear it for each
        other and the later one would skip. Taken before the debouncer and
        receiver locks, never after.
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
            # A skip reports success without asking the receiver, so it must not
            # clear or hide a confirmed failure, this coordinator's or the
            # other's. Costs one read per interval while either is unavailable.
            # Decided under the lock: the other coordinator's listeners run
            # while this one waits for it, and may mark it unavailable.
            force = (
                self._force_next_refresh
                or not self.last_update_success
                or (self.peer is not None and not self.peer.last_update_success)
            )
            try:
                await self._refresh_fn(self.receiver, force=force)
            except UNAVAILABLE_ON as err:
                raise UpdateFailed(
                    f"Error communicating with {self.receiver.name}: {err}"
                ) from err


@callback
def mark_unavailable(coordinator: DenonAvrDataUpdateCoordinator) -> None:
    """Mark a coordinator unavailable after a confirmed connectivity failure.

    For failures outside the refresh cycle, such as a command of an entity's
    own, so availability reflects them without waiting for the next poll.
    Notifies even when already unavailable: the other coordinator may have
    recovered since the last failure.
    """
    coordinator.last_update_success = False
    coordinator.async_update_listeners()
