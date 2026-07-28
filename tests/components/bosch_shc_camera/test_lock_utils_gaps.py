"""Tests for `lock_utils.get_or_create_lock`."""

import asyncio

from homeassistant.components.bosch_shc_camera.lock_utils import get_or_create_lock


def test_creates_lock_when_absent() -> None:
    """A missing key gets a freshly created, stored `asyncio.Lock`."""
    store: dict[str, asyncio.Lock] = {}

    lock = get_or_create_lock(store, "cam-1")

    assert isinstance(lock, asyncio.Lock)
    assert store["cam-1"] is lock


def test_reuses_existing_lock() -> None:
    """An existing key's lock is returned unchanged, not replaced."""
    store: dict[str, asyncio.Lock] = {}
    first = get_or_create_lock(store, "cam-1")

    second = get_or_create_lock(store, "cam-1")

    assert second is first
    assert len(store) == 1


def test_different_keys_get_different_locks() -> None:
    """Distinct keys never share the same lock instance."""
    store: dict[str, asyncio.Lock] = {}

    lock_a = get_or_create_lock(store, "cam-a")
    lock_b = get_or_create_lock(store, "cam-b")

    assert lock_a is not lock_b
