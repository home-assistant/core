"""Cache for the Map tiles integration."""

import asyncio
from collections import OrderedDict
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import time
from typing import Any, Final

from homeassistant.core import HomeAssistant

from .const import CACHE_MAX_BYTES, DOMAIN, MAX_CONCURRENT_FETCHES

# Approximate bookkeeping cost of one entry (key, tuple, Asset, timestamp and
# dict slot), charged so tiny bodies cannot grow the entry count without bound.
_ENTRY_OVERHEAD: Final = 300


@dataclass(frozen=True, slots=True)
class Asset:
    """An upstream response body plus the Content-Encoding it is stored in.

    Kept compressed as upstream sent it, so a dense vector tile is not
    re-compressed for every client that requests it.
    """

    body: bytes
    encoding: str | None
    ttl: float | None = None


type FetchCallback = Callable[[], Coroutine[Any, Any, Asset | None]]


def _entry_size(key: str, asset: Asset) -> int:
    """Return what an entry counts against the size ceiling."""
    return len(asset.body) + len(key) + _ENTRY_OVERHEAD


class MapTilesCache:
    """A bounded in-memory cache of upstream responses, keyed by asset path.

    Entries are never dropped for being stale, so only the size ceiling evicts,
    least recently used first.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the cache."""
        self._hass = hass
        self._max_bytes = CACHE_MAX_BYTES
        self._entries: OrderedDict[str, tuple[Asset, float]] = OrderedDict()
        self._size = 0
        self._fetches: dict[str, asyncio.Task[Asset | None]] = {}
        self._fetch_semaphore = asyncio.Semaphore(MAX_CONCURRENT_FETCHES)

    async def async_get(self, key: str, ttl: int, fetch: FetchCallback) -> Asset | None:
        """Return the entry for key, fetching or refreshing it as needed.

        ttl is the fallback refresh interval, used when the stored asset carries
        no upstream max-age of its own.
        """
        if (entry := self._entries.get(key)) is None:
            return await self._async_fetch(key, fetch)

        self._entries.move_to_end(key)
        asset, stored_at = entry
        if time.monotonic() - stored_at > (ttl if asset.ttl is None else asset.ttl):
            # Serve the stale entry now and refresh in the background, so an
            # upstream outage degrades to slightly old tiles, not to no map.
            self._hass.async_create_background_task(
                self._async_fetch(key, fetch), f"{DOMAIN} refresh {key}"
            )
        return asset

    def _store(self, key: str, asset: Asset) -> None:
        """Store an entry, evicting until back under the size ceiling."""
        if (previous := self._entries.pop(key, None)) is not None:
            self._size -= _entry_size(key, previous[0])

        self._entries[key] = (asset, time.monotonic())
        self._size += _entry_size(key, asset)

        while self._size > self._max_bytes and len(self._entries) > 1:
            evicted_key, (evicted, _stored_at) = self._entries.popitem(last=False)
            self._size -= _entry_size(evicted_key, evicted)

    async def _async_fetch(self, key: str, fetch: FetchCallback) -> Asset | None:
        """Fetch key upstream, joining a fetch already in flight for it."""
        if (pending := self._fetches.get(key)) is None:
            pending = self._hass.async_create_task(
                self._async_fetch_and_store(key, fetch), f"{DOMAIN} fetch {key}"
            )
            if not pending.done():
                self._fetches[key] = pending
                pending.add_done_callback(lambda _task: self._fetches.pop(key, None))

        # Shielded: one client navigating away must not cancel the fetch the
        # others are waiting on.
        return await asyncio.shield(pending)

    async def _async_fetch_and_store(
        self, key: str, fetch: FetchCallback
    ) -> Asset | None:
        """Fetch key upstream and store what comes back."""
        # Bounds parallel upstream requests and the in-flight body memory they
        # hold; the store afterwards is synchronous and needs no slot.
        async with self._fetch_semaphore:
            asset = await fetch()
        if asset is not None:
            self._store(key, asset)
        return asset
