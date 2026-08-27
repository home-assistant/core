"""Tests for the Map tiles cache."""

import asyncio

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.map_tiles.cache import Asset, MapTilesCache
from homeassistant.core import HomeAssistant

TTL = 60


async def test_evicts_least_recently_used(hass: HomeAssistant) -> None:
    """Test that the cache stays inside its ceiling, dropping the coldest first."""
    cache = MapTilesCache(hass, max_bytes=20)
    calls: list[str] = []

    async def fetch(key: str) -> Asset:
        calls.append(key)
        return Asset(b"0123456789", None)

    for key in ("a", "b"):
        await cache.async_get(key, TTL, lambda key=key: fetch(key))
    # Reading "a" leaves "b" as the coldest entry.
    await cache.async_get("a", TTL, lambda: fetch("a"))
    await cache.async_get("c", TTL, lambda: fetch("c"))

    assert calls == ["a", "b", "c"]

    # "a" and "c" are still held; "b" was evicted to make room.
    await cache.async_get("a", TTL, lambda: fetch("a"))
    await cache.async_get("c", TTL, lambda: fetch("c"))
    assert calls == ["a", "b", "c"]

    await cache.async_get("b", TTL, lambda: fetch("b"))
    assert calls == ["a", "b", "c", "b"]


async def test_entry_larger_than_the_ceiling_is_kept(hass: HomeAssistant) -> None:
    """Test that a tile bigger than the whole cache is still served from it."""
    cache = MapTilesCache(hass, max_bytes=10)
    calls: list[str] = []

    async def fetch() -> Asset:
        calls.append("fetched")
        return Asset(b"a dense city tile at a low zoom", None)

    await cache.async_get("big", TTL, fetch)
    await cache.async_get("big", TTL, fetch)

    assert calls == ["fetched"]


async def test_the_encoding_is_cached_with_the_body(hass: HomeAssistant) -> None:
    """Test that a cached asset still knows how its bytes are encoded."""
    cache = MapTilesCache(hass)

    async def fetch() -> Asset:
        return Asset(b"compressed bytes", "gzip")

    assert await cache.async_get("key", TTL, fetch) == Asset(
        b"compressed bytes", "gzip"
    )
    assert await cache.async_get("key", TTL, fetch) == Asset(
        b"compressed bytes", "gzip"
    )


async def test_failed_fetch_is_not_stored(hass: HomeAssistant) -> None:
    """Test that a failure is retried rather than remembered."""
    cache = MapTilesCache(hass)
    calls: list[str] = []

    async def fetch() -> Asset | None:
        calls.append("fetched")
        return None

    assert await cache.async_get("key", TTL, fetch) is None
    assert await cache.async_get("key", TTL, fetch) is None
    assert len(calls) == 2


async def test_concurrent_requests_share_one_fetch(hass: HomeAssistant) -> None:
    """Test that a map view asking for one tile many times asks upstream once."""
    cache = MapTilesCache(hass)
    released = asyncio.Event()
    calls: list[str] = []

    async def fetch() -> Asset:
        calls.append("fetched")
        await released.wait()
        return Asset(b"tile", None)

    waiting = [
        asyncio.create_task(cache.async_get("key", TTL, fetch)) for _ in range(5)
    ]
    await asyncio.sleep(0)
    released.set()

    assert await asyncio.gather(*waiting) == [Asset(b"tile", None)] * 5
    assert calls == ["fetched"]


async def test_a_cancelled_client_does_not_cancel_the_fetch(
    hass: HomeAssistant,
) -> None:
    """Test that one client navigating away leaves the others their tile."""
    cache = MapTilesCache(hass)
    released = asyncio.Event()

    async def fetch() -> Asset:
        await released.wait()
        return Asset(b"tile", None)

    leaving = asyncio.create_task(cache.async_get("key", TTL, fetch))
    staying = asyncio.create_task(cache.async_get("key", TTL, fetch))
    await asyncio.sleep(0)

    leaving.cancel()
    released.set()

    assert await staying == Asset(b"tile", None)


async def test_stale_entry_is_refreshed_behind_the_response(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test that an expired entry answers now and is replaced afterwards."""
    cache = MapTilesCache(hass)
    tiles = [b"first", b"second"]

    async def fetch() -> Asset:
        return Asset(tiles.pop(0), None)

    assert await cache.async_get("key", TTL, fetch) == Asset(b"first", None)

    freezer.tick(TTL + 1)
    assert await cache.async_get("key", TTL, fetch) == Asset(b"first", None)
    await hass.async_block_till_done()

    assert await cache.async_get("key", TTL, fetch) == Asset(b"second", None)
