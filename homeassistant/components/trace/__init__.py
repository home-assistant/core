"""Support for script and automation tracing and debugging."""
from __future__ import annotations

import datetime as dt
from itertools import count
from typing import Any, Deque

from homeassistant.core import Context
from homeassistant.helpers.trace import (
    TraceElement,
    trace_id_get,
    trace_id_set,
    trace_set_child_id,
)
import homeassistant.util.dt as dt_util

from . import websocket_api
from .const import DATA_TRACE, STORED_TRACES
from .utils import LimitedSizeDict

DOMAIN = "trace"


async def async_setup(hass, config):
    """Initialize the trace integration."""
    hass.data[DATA_TRACE] = {}
    websocket_api.async_setup(hass)
    return True


def async_store_trace(hass, trace):
    """Store a trace if its item_id is valid."""
    key = trace.key
    if key[1]:
        traces = hass.data[DATA_TRACE]
        if key not in traces:
            traces[key] = LimitedSizeDict(size_limit=STORED_TRACES)
        traces[key][trace.run_id] = trace


class ActionTrace:
    """Base container for an script or automation trace."""

    _run_ids = count(0)

    def __init__(
        self,
        key: tuple[str, str],
        config: dict[str, Any],
        context: Context,
    ):
        """Container for script trace."""
        self._action_trace: dict[str, Deque[TraceElement]] | None = None
        self._config: dict[str, Any] = config
        self.context: Context = context
        self._error: Exception | None = None
        self._state: str = "running"
        self.run_id: str = str(next(self._run_ids))
        self._timestamp_finish: dt.datetime | None = None
        self._timestamp_start: dt.datetime = dt_util.utcnow()
        self.key: tuple[str, str] = key
        self._variables: dict[str, Any] | None = None
        if trace_id_get():
            trace_set_child_id(self.key, self.run_id)
        trace_id_set((key, self.run_id))

    def set_action_trace(self, trace: dict[str, Deque[TraceElement]]) -> None:
        """Set action trace."""
        self._action_trace = trace

    def set_error(self, ex: Exception) -> None:
        """Set error."""
        self._error = ex

    def set_variables(self, variables: dict[str, Any]) -> None:
        """Set variables."""
        self._variables = variables

    def finished(self) -> None:
        """Set finish time."""
        self._timestamp_finish = dt_util.utcnow()
        self._state = "stopped"

    def as_dict(self) -> dict[str, Any]:
        """Return dictionary version of this ActionTrace."""

        result = self.as_short_dict()

        action_traces = {}
        if self._action_trace:
            for key, trace_list in self._action_trace.items():
                action_traces[key] = [item.as_dict() for item in trace_list]

        result.update(
            {
                "action_trace": action_traces,
                "config": self._config,
                "context": self.context,
                "variables": self._variables,
            }
        )
        if self._error is not None:
            result["error"] = str(self._error)
        return result

    def as_short_dict(self) -> dict[str, Any]:
        """Return a brief dictionary version of this ActionTrace."""

        last_action = None

        if self._action_trace:
            last_action = list(self._action_trace)[-1]

        result = {
            "last_action": last_action,
            "run_id": self.run_id,
            "state": self._state,
            "timestamp": {
                "start": self._timestamp_start,
                "finish": self._timestamp_finish,
            },
            "domain": self.key[0],
            "item_id": self.key[1],
        }
        if self._error is not None:
            result["error"] = str(self._error)
        if last_action is not None:
            result["last_action"] = last_action

        return result
