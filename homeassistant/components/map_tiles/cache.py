"""Cache for the Map tiles integration."""

import asyncio
from collections import OrderedDict
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
import time
from typing import Any

from homeassistant.core import HomeAssistant

from .const import CACHE_MAX_BYTES, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Asset:
    """An upstream response, held in the encoding it is served in.

    Holding the compressed bytes is what stops a dense vector tile from being
    compressed again here for every client that asks for it.
    """

    body: bytes
    encoding: str | None


type FetchCallback = Callable[[], Coroutine[Any, Any, Asset | None]]


class MapTilesCache:
    """A bounded in-memory cache of upstream responses, keyed by asset path.

    Entries are never dropped for being stale, so only the size ceiling evicts,
    least recently used first.
    """

    def __init__(self, hass: HomeAssistant, max_bytes: int = CACHE_MAX_BYTES) -> None:
        """Initialize the cache."""
        self._hass = hass
        self._max_bytes = max_bytes
        self._entries: OrderedDict[str, tuple[Asset, float]] = OrderedDict()
        self._size = 0
        self._fetches: dict[str, asyncio.Task[Asset | None]] = {}

    async def async_get(self, key: str, ttl: int, fetch: FetchCallback) -> Asset | None:
        """Return the entry for key, fetching or refreshing it as needed."""
        if (entry := self._entries.get(key)) is None:
            return await self._async_fetch(key, fetch)

        self._entries.move_to_end(key)
        asset, stored_at = entry
        if time.time() - stored_at > ttl:
            # Behind the response rather than in front of it, so an upstream
            # outage degrades to slightly old tiles, not to no map.
            self._hass.async_create_background_task(
                self._async_fetch(key, fetch), f"{DOMAIN} refresh {key}"
            )
        return asset

    def _store(self, key: str, asset: Asset) -> None:
        """Store an entry, evicting until back under the size ceiling."""
        if (previous := self._entries.pop(key, None)) is not None:
            self._size -= len(previous[0].body)

        self._entries[key] = (asset, time.time())
        self._size += len(asset.body)

        while self._size > self._max_bytes and len(self._entries) > 1:
            _key, (evicted, _stored_at) = self._entries.popitem(last=False)
            self._size -= len(evicted.body)

    async def _async_fetch(self, key: str, fetch: FetchCallback) -> Asset | None:
        """Fetch key upstream, joining a fetch already in flight for it."""
        if (pending := self._fetches.get(key)) is None:
            # Not eager: the task drops itself from _fetches when it finishes,
            # which has to happen after it was put there.
            pending = self._fetches[key] = self._hass.async_create_task(
                self._async_fetch_and_store(key, fetch),
                f"{DOMAIN} fetch {key}",
                eager_start=False,
            )

        # Shielded: one client navigating away must not cancel the fetch the
        # others are waiting on.
        return await asyncio.shield(pending)

    async def _async_fetch_and_store(
        self, key: str, fetch: FetchCallback
    ) -> Asset | None:
        """Fetch key upstream and store what comes back."""
        try:
            if (asset := await fetch()) is not None:
                self._store(key, asset)
        finally:
            # Not from a done callback, which would leave a finished task in
            # here to be replayed as a result.
            del self._fetches[key]
        return asset
