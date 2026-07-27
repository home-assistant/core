"""Shared per-camera lock helper.

Used across coordinator/slow_tier/tick_bootstrap so concurrent writes to the
same Bosch cloud endpoint serialize on the same lock instance.
"""

import asyncio
from typing import Any


def _get_cam_lock(coordinator: Any, lock_attr: str, cam_id: str) -> asyncio.Lock:
    """Return (lazily creating) a per-camera asyncio.Lock.

    Stored on the coordinator under ``lock_attr``, keyed by ``cam_id``.

    Several entity classes across switch.py/number.py/light.py can share one
    Bosch cloud endpoint that requires a full-body PUT (multiple sibling
    fields in one object — e.g. audioEnabled+speakerLevel+microphoneLevel on
    /audio). Concurrent read-modify-write calls for two different fields on
    the SAME endpoint must serialize on the SAME lock instance and merge only
    their own field back into the shared cache afterward, or one write's
    stale snapshot can silently revert the other's just-written field.
    """
    locks: dict[str, asyncio.Lock] | None = getattr(coordinator, lock_attr, None)
    if locks is None:
        locks = {}
        setattr(coordinator, lock_attr, locks)
    lock = locks.get(cam_id)
    if lock is None:
        lock = asyncio.Lock()
        locks[cam_id] = lock
    return lock
