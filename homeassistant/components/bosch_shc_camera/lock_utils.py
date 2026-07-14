"""Get-or-create per-key ``asyncio.Lock`` helper.

The coordinator (``__init__.py``) independently grew several near-identical
copies of the same "get-or-create a lock for this key in my dict" pattern —
``_get_stream_lock``, ``_get_rcp_session_lock``, ``_get_nvr_recorder_lock``,
``_get_nvr_clip_assembly_lock``, ``async_fetch_live_snapshot``'s
``_snapshot_fetch_locks`` lookup, the go2rtc re-registration coalescing
lookup, and ``async_fetch_fresh_event_snapshot``'s ``_fresh_snap_locks``
lookup — as new per-camera/per-session locking needs were bolted on release
after release. This collapses all of them into one function each now
delegates to.

Deliberately NOT applied to the go2rtc setup lock in ``async_setup_entry``
(``hass.data.setdefault(f"{DOMAIN}_go2rtc_init_lock", asyncio.Lock())``) —
that one is a single fixed-key lock scoped to ``hass.data`` for
cross-config-entry serialization, not a per-key registry the coordinator
owns, so forcing it through this helper would be a shape mismatch rather
than real deduplication.

``store`` accepts any ``MutableMapping`` (not just a plain ``dict``) since
Session-State-Facade Slice 4 (``docs/stream-perf-stability-refactor-plan.md``)
backs five per-cam_id coordinator lock dicts (``_stream_locks``/
``_nvr_recorder_locks``/``_snapshot_fetch_locks``/
``_nvr_clip_assembly_locks``/``_fresh_snap_locks``) with
``session_state.CacheFieldView`` instead (``_go2rtc_reregister_locks`` was a
sixth, removed 2026-07-14 when the manual go2rtc PUT/DELETE registration it
serialized was replaced by HA-core's native lazy auto-registration,
HA-Core-submission-prep) — a
full ``MutableMapping`` whose ``.get()``/``__setitem__`` behave identically
to a plain dict's for this helper's purposes (verified in
``tests/test_session_state_facade_slice4.py``, including that a lock's
IDENTITY survives across repeated calls). Test fixtures across the suite
still pass plain ``dict[str, asyncio.Lock]`` stand-ins directly, which
continue to work unchanged since ``dict`` satisfies ``MutableMapping`` too.
"""

from __future__ import annotations

import asyncio
from collections.abc import MutableMapping


def get_or_create_lock(
    store: MutableMapping[str, asyncio.Lock], key: str
) -> asyncio.Lock:
    """Return the ``asyncio.Lock`` for ``key`` in ``store``, creating it if absent.

    Safe under asyncio: check-then-insert has no ``await`` between the two
    steps, so concurrent coroutines cannot interleave here.
    """
    lock = store.get(key)
    if lock is None:
        lock = asyncio.Lock()
        store[key] = lock
    return lock
