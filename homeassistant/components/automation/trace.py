"""Trace support for automation."""
from __future__ import annotations

from contextlib import contextmanager
import datetime as dt
from itertools import count
from typing import Any, Deque

from homeassistant.components.trace.const import DATA_TRACE, STORED_TRACES
from homeassistant.components.trace.utils import LimitedSizeDict
from homeassistant.core import Context
from homeassistant.helpers.trace import TraceElement, trace_id_set
from homeassistant.util import dt as dt_util

# mypy: allow-untyped-calls, allow-untyped-defs
# mypy: no-check-untyped-defs, no-warn-return-any


class AutomationTrace:
    """Container for automation trace."""

    _run_ids = count(0)

    def __init__(
        self,
        unique_id: str | None,
        config: dict[str, Any],
        context: Context,
    ):
        """Container for automation trace."""
        self._action_trace: dict[str, Deque[TraceElement]] | None = None
        self._condition_trace: dict[str, Deque[TraceElement]] | None = None
        self._config: dict[str, Any] = config
        self.context: Context = context
        self._error: Exception | None = None
        self._state: str = "running"
        self.run_id: str = str(next(self._run_ids))
        self._timestamp_finish: dt.datetime | None = None
        self._timestamp_start: dt.datetime = dt_util.utcnow()
        self._unique_id: str | None = unique_id
        self._variables: dict[str, Any] | None = None

    def set_action_trace(self, trace: dict[str, Deque[TraceElement]]) -> None:
        """Set action trace."""
        self._action_trace = trace

    def set_condition_trace(self, trace: dict[str, Deque[TraceElement]]) -> None:
        """Set condition trace."""
        self._condition_trace = trace

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
        """Return dictionary version of this AutomationTrace."""

        result = self.as_short_dict()

        action_traces = {}
        condition_traces = {}
        if self._action_trace:
            for key, trace_list in self._action_trace.items():
                action_traces[key] = [item.as_dict() for item in trace_list]

        if self._condition_trace:
            for key, trace_list in self._condition_trace.items():
                condition_traces[key] = [item.as_dict() for item in trace_list]

        result.update(
            {
                "action_trace": action_traces,
                "condition_trace": condition_traces,
                "config": self._config,
                "context": self.context,
                "variables": self._variables,
            }
        )
        if self._error is not None:
            result["error"] = str(self._error)
        return result

    def as_short_dict(self) -> dict[str, Any]:
        """Return a brief dictionary version of this AutomationTrace."""

        last_action = None
        last_condition = None
        trigger = None

        if self._action_trace:
            last_action = list(self._action_trace)[-1]
        if self._condition_trace:
            last_condition = list(self._condition_trace)[-1]
        if self._variables:
            trigger = self._variables.get("trigger", {}).get("description")

        result = {
            "automation_id": self._unique_id,
            "last_action": last_action,
            "last_condition": last_condition,
            "run_id": self.run_id,
            "state": self._state,
            "timestamp": {
                "start": self._timestamp_start,
                "finish": self._timestamp_finish,
            },
            "trigger": trigger,
            "unique_id": self._unique_id,
        }
        if self._error is not None:
            result["error"] = str(self._error)
        if last_action is not None:
            result["last_action"] = last_action
            result["last_condition"] = last_condition

        return result


@contextmanager
def trace_automation(hass, unique_id, config, context):
    """Trace action execution of automation with automation_id."""
    automation_trace = AutomationTrace(unique_id, config, context)
    trace_id_set((unique_id, automation_trace.run_id))

    if unique_id:
        automation_traces = hass.data[DATA_TRACE]
        if unique_id not in automation_traces:
            automation_traces[unique_id] = LimitedSizeDict(size_limit=STORED_TRACES)
        automation_traces[unique_id][automation_trace.run_id] = automation_trace

    try:
        yield automation_trace
    except Exception as ex:  # pylint: disable=broad-except
        if unique_id:
            automation_trace.set_error(ex)
        raise ex
    finally:
        if unique_id:
            automation_trace.finished()
