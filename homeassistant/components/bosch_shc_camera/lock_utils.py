"""Get-or-create per-key ``asyncio.Lock`` helper.

The coordinator (``coordinator.py``) independently grew several near-identical
copies of the same "get-or-create a lock for this key in my dict" pattern —
``_get_rcp_session_lock``, ``async_fetch_live_snapshot``'s
``_snapshot_fetch_locks`` lookup, and ``async_fetch_fresh_event_snapshot``'s
``_fresh_snap_locks`` lookup — as new per-camera locking needs were bolted on
release after release. This collapses all of them into one function each now
delegates to.

``store`` accepts any ``MutableMapping`` (not just a plain ``dict``) so a
future per-cam_id lock dict backed by something other than a plain dict
can still use this helper without changes — its ``.get()``/``__setitem__``
behave identically to a plain dict's for this helper's purposes. Test
fixtures across the suite pass plain ``dict[str, asyncio.Lock]`` stand-ins
directly, which work unchanged since ``dict`` satisfies ``MutableMapping``
too.
"""

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
