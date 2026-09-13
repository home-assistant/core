"""DataUpdateCoordinators for Denon AVR.

Two separate coordinators, not one, because the existing "Update
Audyssey settings" option needs to keep meaning what it already means
in media_player.py: whether Audyssey data (which can reportedly take
up to ~10s to fetch on some receivers) is refreshed on a recurring
schedule at all. A single coordinator can't have one interval that's
both "always on" (for general status) and "off unless opted in" (for
Audyssey) at the same time.
"""

import asyncio
from collections.abc import Callable, Coroutine
from datetime import timedelta
import logging
from typing import Any, override

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
from homeassistant.core import HomeAssistant
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


async def async_refresh_status(receiver: DenonAVR) -> None:
    """Refresh general receiver status for every configured zone.

    Skips the HTTP poll if Telnet is already healthy and keeping
    everything current - that connection state is shared across zones
    (it lives on the underlying device, not per zone), so it only
    needs checking once regardless of how many zones are enabled.
    """
    if receiver.telnet_connected and receiver.telnet_healthy:
        return
    for zone_receiver in receiver.zones.values():
        await zone_receiver.async_update()


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
        refresh_fn: Callable[[DenonAVR], Coroutine[Any, Any, None]],
    ) -> None:
        """Initialize the coordinator.

        `lock` is created once per config entry and shared with the
        other coordinator, every select/switch entity, and
        media_player.py's own commands - the receiver's HTTP/Telnet
        interface can't safely handle concurrent requests, and nothing
        else ties all of those together on its own. It can't be looked
        up from the receiver object instead (e.g. via a
        WeakKeyDictionary keyed by it): denonavr's attrs classes define
        a field-based __eq__ without a matching __hash__, so instances
        are unhashable and can't be dict/weak-ref keys at all.
        """
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{DOMAIN}_{name}",
            config_entry=config_entry,
            update_interval=update_interval,
            # immediate=False rather than the library default (True):
            # the receiver needs a moment to settle after a command
            # anyway, so a short wait before the post-action confirm is
            # correct, not just tolerated - and it coalesces
            # near-simultaneous actions into one shared refresh instead
            # of a separate one each. See the const.py comment.
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

    @override
    async def _async_update_data(self) -> None:
        """Refresh the receiver via this coordinator's refresh_fn."""
        async with self.lock:
            try:
                await self._refresh_fn(self.receiver)
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
