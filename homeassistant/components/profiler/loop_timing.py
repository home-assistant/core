"""Time the callbacks of the event loop.

Every step of the event loop, a task step included, runs through
asyncio.events.Handle._run. While timing is on, a wrapper around it charges
the wall time of each callback to what ran: a task step to its coroutine
and the class of its `self`, a HassJob to its target, anything else to its
function or method and class, each split by the config entry whose context
it runs in. While timing is off, Handle._run is the original.
"""

import asyncio
from asyncio import events
from collections import deque
from collections.abc import Callable
from functools import partial
import time
from types import ModuleType
from typing import Any

from homeassistant.config_entries import current_entry
from homeassistant.core import HassJob
from homeassistant.util import dt as dt_util

# asyncio's own idea of a slow callback in debug mode
DEFAULT_THRESHOLD_MS = 100.0
MAX_SLOW_CALLBACKS = 100
# Only code compiled at runtime can add rows without bound
MAX_ROWS = 10_000

type _Key = tuple[Any, type | None, str | None]
_OTHER: _Key = ("other", None, None)


class _Row:
    """What one owner did on the loop."""

    __slots__ = ("count", "label", "max_at", "max_ns", "total_ns")

    def __init__(self, label: str) -> None:
        self.label = label
        self.count = 0
        self.total_ns = 0
        self.max_ns = 0
        self.max_at = 0.0


def _label(func: Any, code: Any, cls: type | None, module: str | None) -> str:
    """Return module.Class.function from the live objects of a callback."""
    if cls is not None:
        name = code.co_name if code is not None else getattr(func, "__name__", "?")
        return f"{cls.__module__}.{cls.__qualname__}.{name}"
    if code is not None:
        return f"{module}.{code.co_qualname}" if module else code.co_qualname
    name = getattr(func, "__qualname__", None) or type(func).__qualname__
    return f"{module or type(func).__module__}.{name}"


class LoopTiming:
    """Record how long each callback holds the event loop."""

    def __init__(self, loop: asyncio.AbstractEventLoop, threshold_ms: float) -> None:
        """Initialize; start() installs the wrapper."""
        self._loop = loop
        self._threshold_ns = int(threshold_ms * 1_000_000)
        self._rows: dict[_Key, _Row] = {}
        # Numbered, so a reader can tell new entries from ones it has seen
        self._slow: deque[tuple[int, float, int, str, str | None]] = deque(
            maxlen=MAX_SLOW_CALLBACKS
        )
        self._slow_seq = 0
        self._original: Callable[[Any], None] | None = None
        self._wrapper: Callable[[Any], None] | None = None
        self.errors = 0
        self.started_at = 0.0

    def start(self) -> None:
        """Install the wrapper on Handle._run."""
        if self._wrapper is not None:
            return
        original = events.Handle._run  # noqa: SLF001
        loop = self._loop
        rows = self._rows
        slow = self._slow
        threshold = self._threshold_ns
        perf = time.perf_counter_ns
        wall = time.time
        task_type = asyncio.Task

        # One function with everything inline: it runs once per callback
        def _run(handle: Any) -> None:
            if handle._loop is not loop:  # noqa: SLF001
                original(handle)
                return
            row = None
            key: _Key = _OTHER
            # Nothing in here may escape into the loop, hence one wide try
            try:
                # Before the run: a callback that cancels its handle drops
                # _callback, and a coroutine that finishes drops its frame
                func = handle._callback  # noqa: SLF001
                owner = getattr(func, "__self__", None)
                module = None
                if isinstance(owner, task_type):
                    coro: Any = owner.get_coro()
                    code = getattr(coro, "cr_code", None)
                    frame = getattr(coro, "cr_frame", None)
                    if frame is not None:
                        owner = frame.f_locals.get("self")
                        module = frame.f_globals.get("__name__")
                    else:
                        owner = None
                    if code is None:
                        # Not a coroutine: an async generator step, say
                        func = coro
                else:
                    args = handle._args  # noqa: SLF001
                    if args and isinstance(args[-1], HassJob):
                        func = args[-1].target
                    while isinstance(func, partial):
                        func = func.func
                    owner = getattr(func, "__self__", None)
                    if owner is None and not hasattr(func, "__qualname__"):
                        # A callable instance is charged to its class
                        owner = func
                        func = type(func).__call__
                    func = getattr(func, "__func__", func)
                    code = getattr(func, "__code__", None)
                    module = getattr(func, "__module__", None)
                if owner is None or isinstance(owner, ModuleType):
                    cls = None
                else:
                    cls = owner if isinstance(owner, type) else type(owner)
                entry = handle._context.get(current_entry)  # noqa: SLF001
                # C code has no code object; module and qualified name must do
                key = (
                    code
                    if code is not None
                    else (
                        module or type(func).__module__,
                        getattr(func, "__qualname__", type(func).__qualname__),
                    ),
                    cls,
                    entry.entry_id if entry is not None else None,
                )
                if (row := rows.get(key)) is None:
                    if len(rows) >= MAX_ROWS:
                        key = _OTHER
                        row = rows.get(key)
                    if row is None:
                        label = (
                            "other callbacks"
                            if key is _OTHER
                            else _label(func, code, cls, module)
                        )
                        row = rows[key] = _Row(label)
            except Exception:  # noqa: BLE001
                self.errors += 1
            start = perf()
            try:
                original(handle)
            finally:
                if row is not None:
                    elapsed = perf() - start
                    row.count += 1
                    row.total_ns += elapsed
                    if elapsed > row.max_ns:
                        row.max_ns = elapsed
                        row.max_at = wall()
                    if elapsed >= threshold:
                        self._slow_seq += 1
                        slow.append(
                            (self._slow_seq, wall(), elapsed, row.label, key[2])
                        )

        self._original = original
        self._wrapper = _run
        self.started_at = time.time()
        events.Handle._run = _run  # type: ignore[method-assign, assignment]  # noqa: SLF001

    def stop(self) -> None:
        """Remove the wrapper, if it is still in place."""
        if self._wrapper is None:
            return
        if events.Handle._run is self._wrapper:  # noqa: SLF001
            events.Handle._run = self._original  # type: ignore[method-assign, assignment]  # noqa: SLF001
        self._wrapper = None
        self._original = None

    def report(self) -> dict[str, Any]:
        """Return what was recorded so far, busiest owners first."""
        return {
            "since": dt_util.utc_from_timestamp(self.started_at).isoformat(),
            "threshold_ms": self._threshold_ns / 1_000_000,
            "errors": self.errors,
            "callbacks": [
                {
                    "callback": row.label,
                    "config_entry": key[2],
                    "count": row.count,
                    "total_ms": round(row.total_ns / 1_000_000, 1),
                    "max_ms": round(row.max_ns / 1_000_000, 1),
                    "max_at": dt_util.utc_from_timestamp(row.max_at).isoformat(),
                }
                for key, row in sorted(
                    self._rows.items(), key=lambda item: -item[1].total_ns
                )
                if row.count
            ],
            "slow": [
                {
                    "seq": seq,
                    "at": dt_util.utc_from_timestamp(at).isoformat(),
                    "ms": round(elapsed / 1_000_000, 1),
                    "callback": label,
                    "config_entry": entry,
                }
                for seq, at, elapsed, label, entry in self._slow
            ],
        }


def format_report(report: dict[str, Any]) -> str:
    """Return a report as text for the log."""

    def where(row: dict[str, Any]) -> str:
        if (entry := row.get("entry")) is None:
            return ""
        return f" [{entry['domain']}: {entry['title']}]"

    lines = [f"Event loop callbacks since {report['since']}, busiest first:"]
    lines.extend(
        f"  {row['callback']}{where(row)}: {row['count']} calls,"
        f" {row['total_ms']} ms total, longest {row['max_ms']} ms at {row['max_at']}"
        for row in report["callbacks"][:50]
    )
    if report["slow"]:
        lines.append(f"Callbacks over {report['threshold_ms']} ms:")
        lines.extend(
            f"  {row['at']}: {row['ms']} ms {row['callback']}{where(row)}"
            for row in report["slow"]
        )
    if report["errors"]:
        lines.append(f"Callbacks that could not be attributed: {report['errors']}")
    return "\n".join(lines)
