"""Containers for a script or automation trace."""
from __future__ import annotations

import abc
from collections import deque
import datetime as dt
from typing import Any

from homeassistant.core import Context
from homeassistant.helpers.trace import (
    TraceElement,
    script_execution_get,
    trace_id_get,
    trace_id_set,
    trace_set_child_id,
)
import homeassistant.util.dt as dt_util
import homeassistant.util.uuid as uuid_util


class BaseTrace(abc.ABC):
    """Base container for a script or automation trace."""

    context: Context
    key: str
    run_id: str

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

    def as_short_dict(self) -> dict[str, Any]:
        """Return a brief dictionary version of this ActionTrace."""
        if self._short_dict:
            return self._short_dict

        last_step = None

        if self._trace:
            last_step = list(self._trace)[-1]
        domain, item_id = self.key.split(".", 1)

        result = {
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
        self._dict = extended_dict
        self._short_dict = short_dict

    def as_extended_dict(self) -> dict[str, Any]:
        """Return an extended dictionary version of this RestoredTrace."""
        return self._dict  # type: ignore[no-any-return]

    def as_short_dict(self) -> dict[str, Any]:
        """Return a brief dictionary version of this RestoredTrace."""
        return self._short_dict  # type: ignore[no-any-return]
