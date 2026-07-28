"""Tests for `guards._get_cam_lock`."""

import asyncio
from types import SimpleNamespace

from homeassistant.components.bosch_shc_camera.guards import _get_cam_lock


def test_creates_lock_dict_when_attr_absent() -> None:
    """No pre-existing `lock_attr` dict on the coordinator gets created lazily."""
    coordinator = SimpleNamespace()

    lock = _get_cam_lock(coordinator, "audio_locks", "cam-1")

    assert isinstance(lock, asyncio.Lock)
    assert coordinator.audio_locks == {"cam-1": lock}


def test_reuses_existing_lock_for_same_camera() -> None:
    """Two calls for the same lock_attr+cam_id return the identical lock."""
    coordinator = SimpleNamespace(audio_locks={})

    first = _get_cam_lock(coordinator, "audio_locks", "cam-1")
    second = _get_cam_lock(coordinator, "audio_locks", "cam-1")

    assert first is second


def test_different_cam_ids_get_different_locks() -> None:
    """Two cameras sharing one lock_attr dict never share a lock instance."""
    coordinator = SimpleNamespace(audio_locks={})

    lock_a = _get_cam_lock(coordinator, "audio_locks", "cam-a")
    lock_b = _get_cam_lock(coordinator, "audio_locks", "cam-b")

    assert lock_a is not lock_b
    assert coordinator.audio_locks == {"cam-a": lock_a, "cam-b": lock_b}


def test_different_lock_attrs_are_independent() -> None:
    """Two distinct lock_attr dicts on the same coordinator don't collide."""
    coordinator = SimpleNamespace()

    audio_lock = _get_cam_lock(coordinator, "audio_locks", "cam-1")
    light_lock = _get_cam_lock(coordinator, "light_locks", "cam-1")

    assert audio_lock is not light_lock
    assert coordinator.audio_locks == {"cam-1": audio_lock}
    assert coordinator.light_locks == {"cam-1": light_lock}
