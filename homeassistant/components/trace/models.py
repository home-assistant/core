"""Containers for a script or automation trace."""

import abc
from collections import deque
from collections.abc import Iterator
from dataclasses import dataclass
import datetime as dt
from typing import Any, Literal, cast, override

from homeassistant.core import Context
from homeassistant.helpers.trace import (
    TraceElement,
    script_execution_get,
    trace_id_get,
    trace_id_set,
    trace_set_child_id,
)
from homeassistant.util import dt as dt_util, uuid as uuid_util
from homeassistant.util.limited_size_dict import LimitedSizeDict

type TraceData = dict[str, TraceBuckets]

type TraceBucketKey = Literal[
    "running",
    "not_triggered",
    "finished",
    "aborted",
    "cancelled",
    "failed_conditions",
    "failed_single",
    "failed_max_runs",
    "error",
    "unknown",
]

FINAL_TRACE_BUCKETS: tuple[TraceBucketKey, ...] = (
    "finished",
    "aborted",
    "cancelled",
    "failed_conditions",
    "failed_single",
    "failed_max_runs",
    "error",
)

TRACE_BUCKET_KEYS: tuple[TraceBucketKey, ...] = (
    "running",
    "not_triggered",
    *FINAL_TRACE_BUCKETS,
    "unknown",
)


class BaseTrace(abc.ABC):
    """Base container for a script or automation trace."""

    context: Context
    key: str
    run_id: str
    # True for traces recording that a trigger evaluated a relevant change but
    # did not fire. These are counted separately from actual runs.
    not_triggered: bool = False

    def as_dict(self) -> dict[str, Any]:
        """Return an dictionary version of this ActionTrace for saving."""
        return {
            "extended_dict": self.as_extended_dict(),
            "short_dict": self.as_short_dict(),
        }

    @abc.abstractmethod
    def as_extended_dict(self) -> dict[str, Any]:
        """Return an extended dictionary version of this ActionTrace."""

    @abc.abstractmethod
    def as_short_dict(self) -> dict[str, Any]:
        """Return a brief dictionary version of this ActionTrace."""

    @abc.abstractmethod
    def bucket_key(self) -> TraceBucketKey:
        """Return the storage bucket for this trace."""

    @property
    @abc.abstractmethod
    def timestamp_start(self) -> dt.datetime:
        """Return when the trace began."""


@dataclass(slots=True)
class TraceBuckets:
    """Independently retained trace buckets for one automation/script."""

    buckets: dict[TraceBucketKey, LimitedSizeDict[str, BaseTrace]]

    def bucket(self, key: TraceBucketKey) -> LimitedSizeDict[str, BaseTrace]:
        """Return a trace bucket."""
        return self.buckets[key]

    def set_size_limit(self, size_limit: int) -> None:
        """Apply the configured retention limit to every bucket."""
        for bucket in self.buckets.values():
            bucket.size_limit = size_limit

    def all_traces(self) -> Iterator[BaseTrace]:
        """Yield runs by start time, then not-triggered traces."""
        runs = (
            trace
            for bucket_key, bucket in self.buckets.items()
            if bucket_key != "not_triggered"
            for trace in bucket.values()
        )

        yield from sorted(
            runs,
            key=lambda trace: trace.timestamp_start,
        )

        yield from self.buckets["not_triggered"].values()

    def get(self, run_id: str) -> BaseTrace | None:
        """Return a trace by run ID from any bucket."""
        for bucket in self.buckets.values():
            if trace := bucket.get(run_id):
                return trace
        return None


class ActionTrace(BaseTrace):
    """Base container for a script or automation trace."""

    _domain: str | None = None

    def __init__(
        self,
        item_id: str | None,
        config: dict[str, Any] | None,
        blueprint_inputs: dict[str, Any] | None,
        context: Context,
    ) -> None:
        """Container for script trace."""
        self._trace: dict[str, deque[TraceElement]] | None = None
        self._config = config
        self._blueprint_inputs = blueprint_inputs
        self.context: Context = context
        self._error: Exception | None = None
        self._state: str = "running"
        self._script_execution: str | None = None
        self.run_id: str = uuid_util.random_uuid_hex()
        self._timestamp_finish: dt.datetime | None = None
        self._timestamp_start: dt.datetime = dt_util.utcnow()
        self.key = f"{self._domain}.{item_id}"
        self._dict: dict[str, Any] | None = None
        self._short_dict: dict[str, Any] | None = None
        if trace_id_get():
            trace_set_child_id(self.key, self.run_id)
        trace_id_set((self.key, self.run_id))

    def set_trace(self, trace: dict[str, deque[TraceElement]] | None) -> None:
        """Set action trace."""
        self._trace = trace

    def set_error(self, ex: Exception) -> None:
        """Set error."""
        self._error = ex

    def finished(self) -> None:
        """Set finish time."""
        self._timestamp_finish = dt_util.utcnow()
        self._state = "stopped"
        self._script_execution = script_execution_get()

    @property
    @override
    def timestamp_start(self) -> dt.datetime:
        """Return when this trace began."""
        return self._timestamp_start

    @override
    def bucket_key(self) -> TraceBucketKey:
        """Return the trace's current storage bucket."""
        if self.not_triggered:
            return "not_triggered"

        if self._state != "stopped":
            return "running"

        if self._script_execution in FINAL_TRACE_BUCKETS:
            return self._script_execution

        return "error"

    @override
    def as_extended_dict(self) -> dict[str, Any]:
        """Return an extended dictionary version of this ActionTrace."""
        if self._dict:
            return self._dict

        result = dict(self.as_short_dict())

        traces = {}
        if self._trace:
            for key, trace_list in self._trace.items():
                traces[key] = [item.as_dict() for item in trace_list]

        result.update(
            {
                "trace": traces,
                "config": self._config,
                "blueprint_inputs": self._blueprint_inputs,
                "context": self.context,
            }
        )

        if self._state == "stopped":
            # Execution has stopped, save the result
            self._dict = result
        return result

    @override
    def as_short_dict(self) -> dict[str, Any]:
        """Return a brief dictionary version of this ActionTrace."""
        if self._short_dict:
            return self._short_dict

        last_step = None

        if self._trace:
            last_step = list(self._trace)[-1]
        domain, item_id = self.key.split(".", 1)

        result: dict[str, Any] = {
            "last_step": last_step,
            "run_id": self.run_id,
            "state": self._state,
            "script_execution": self._script_execution,
            "timestamp": {
                "start": self._timestamp_start,
                "finish": self._timestamp_finish,
            },
            "domain": domain,
            "item_id": item_id,
        }
        if self.not_triggered:
            result["not_triggered"] = True
        if self._error is not None:
            result["error"] = str(self._error)

        if self._state == "stopped":
            # Execution has stopped, save the result
            self._short_dict = result
        return result


class RestoredTrace(BaseTrace):
    """Container for a restored script or automation trace."""

    def __init__(self, data: dict[str, Any]) -> None:
        """Restore from dict."""
        extended_dict = data["extended_dict"]
        short_dict = data["short_dict"]
        context = Context(
            user_id=extended_dict["context"]["user_id"],
            parent_id=extended_dict["context"]["parent_id"],
            id=extended_dict["context"]["id"],
        )
        self.context = context
        self.key = f"{extended_dict['domain']}.{extended_dict['item_id']}"
        self.run_id = extended_dict["run_id"]
        self.not_triggered = short_dict.get("not_triggered", False)

        timestamp_start = short_dict["timestamp"]["start"]

        parsed_timestamp_start: dt.datetime | None = None
        if isinstance(timestamp_start, dt.datetime):
            parsed_timestamp_start = timestamp_start
        else:
            parsed_timestamp_start = dt_util.parse_datetime(timestamp_start)

        if parsed_timestamp_start is None:
            raise ValueError(f"Invalid trace start timestamp: {timestamp_start!r}")
        self._timestamp_start = parsed_timestamp_start

        self._dict = extended_dict
        self._short_dict = short_dict

    @override
    def as_extended_dict(self) -> dict[str, Any]:
        """Return an extended dictionary version of this RestoredTrace."""
        return self._dict  # type: ignore[no-any-return]

    @override
    def as_short_dict(self) -> dict[str, Any]:
        """Return a brief dictionary version of this RestoredTrace."""
        return self._short_dict  # type: ignore[no-any-return]

    @override
    def bucket_key(self) -> TraceBucketKey:
        """Return the storage bucket for this restored trace."""
        if self.not_triggered:
            return "not_triggered"

        script_execution = self._short_dict.get("script_execution")
        if script_execution in FINAL_TRACE_BUCKETS:
            return cast(TraceBucketKey, script_execution)

        return "unknown"

    @property
    @override
    def timestamp_start(self) -> dt.datetime:
        """Return when this restored trace began."""
        return self._timestamp_start
