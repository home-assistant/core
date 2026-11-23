"""Tests for the Map tiles cache."""

import asyncio
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.map_tiles.cache import (
    _ENTRY_OVERHEAD,
    Asset,
    MapTilesCache,
)
from homeassistant.core import HomeAssistant

_CACHE = "homeassistant.components.map_tiles.cache"

TTL = 60

BODY = b"0123456789"
# What one entry with a single-character key counts against the ceiling.
ENTRY_COST = len(BODY) + 1 + _ENTRY_OVERHEAD


async def test_evicts_least_recently_used(hass: HomeAssistant) -> None:
    """Test that the cache stays inside its ceiling, dropping the coldest first."""
    with patch(f"{_CACHE}.CACHE_MAX_BYTES", 2 * ENTRY_COST):
        cache = MapTilesCache(hass)
    calls: list[str] = []

    async def fetch(key: str) -> Asset:
        calls.append(key)
        return Asset(BODY, None)

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
    with patch(f"{_CACHE}.CACHE_MAX_BYTES", 10):
        cache = MapTilesCache(hass)
    calls: list[str] = []

    async def fetch() -> Asset:
        calls.append("fetched")
        return Asset(b"a dense city tile at a low zoom", None)

    await cache.async_get("big", TTL, fetch)
    await cache.async_get("big", TTL, fetch)

    assert calls == ["fetched"]


async def test_empty_bodies_count_against_the_ceiling(hass: HomeAssistant) -> None:
    """Test that entries with empty bodies cannot grow the cache without bound."""
    with patch(f"{_CACHE}.CACHE_MAX_BYTES", 3 * (1 + _ENTRY_OVERHEAD)):
        cache = MapTilesCache(hass)
    calls: list[str] = []

    async def fetch(key: str) -> Asset:
        calls.append(key)
        return Asset(b"", None)

    for key in ("a", "b", "c", "d", "e"):
        await cache.async_get(key, TTL, lambda key=key: fetch(key))

    # The per-entry overhead pushed "a" out despite its zero-length body.
    await cache.async_get("a", TTL, lambda: fetch("a"))
    assert calls == ["a", "b", "c", "d", "e", "a"]


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


async def test_a_cancelled_fetch_does_not_poison_the_key(hass: HomeAssistant) -> None:
    """Test that a key can be fetched again after its fetch task was cancelled."""
    cache = MapTilesCache(hass)
    released = asyncio.Event()
    calls: list[str] = []

    async def fetch() -> Asset:
        calls.append("fetched")
        await released.wait()
        return Asset(b"tile", None)

    waiting = asyncio.create_task(cache.async_get("key", TTL, fetch))
    await asyncio.sleep(0)

    # Cancel the fetch task itself, as a shutdown would.
    cache._fetches["key"].cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiting

    released.set()
    assert await cache.async_get("key", TTL, fetch) == Asset(b"tile", None)
    assert len(calls) == 2


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


async def test_asset_ttl_overrides_the_fallback(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test that an asset's own ttl decides staleness, not the caller's fallback."""
    cache = MapTilesCache(hass)
    tiles = [b"first", b"second"]

    async def fetch() -> Asset:
        return Asset(tiles.pop(0), None, ttl=TTL)

    # The fallback is ten times the asset's own ttl, so only the latter can
    # explain a refresh landing right after TTL elapses.
    assert await cache.async_get("key", 10 * TTL, fetch) == Asset(b"first", None, TTL)

    freezer.tick(TTL + 1)
    assert await cache.async_get("key", 10 * TTL, fetch) == Asset(b"first", None, TTL)
    await hass.async_block_till_done()

    assert await cache.async_get("key", 10 * TTL, fetch) == Asset(b"second", None, TTL)


async def test_concurrent_fetches_are_bounded(hass: HomeAssistant) -> None:
    """Test that only so many upstream fetches run at once."""
    with patch(f"{_CACHE}.MAX_CONCURRENT_FETCHES", 2):
        cache = MapTilesCache(hass)
    started = 0
    release = asyncio.Event()

    async def fetch() -> Asset:
        nonlocal started
        started += 1
        await release.wait()
        return Asset(b"tile", None)

    tasks = [
        asyncio.create_task(cache.async_get(key, TTL, fetch))
        for key in ("a", "b", "c", "d", "e")
    ]
    # Let every task run up to the semaphore; only two get past it to fetch().
    for _ in range(10):
        await asyncio.sleep(0)
    assert started == 2

    release.set()
    assert await asyncio.gather(*tasks) == [Asset(b"tile", None)] * 5
    assert started == 5
