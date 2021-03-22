"""Trace support for automation."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Deque

from homeassistant.components.trace.const import DATA_TRACE, STORED_TRACES
from homeassistant.components.trace.utils import LimitedSizeDict
from homeassistant.core import Context
from homeassistant.helpers.trace import ActionTrace, TraceElement, trace_id_set

# mypy: allow-untyped-calls, allow-untyped-defs
# mypy: no-check-untyped-defs, no-warn-return-any


class AutomationTrace(ActionTrace):
    """Container for automation trace."""

    def __init__(
        self,
        key: tuple[str, str],
        config: dict[str, Any],
        context: Context,
    ):
        """Container for automation trace."""
        super().__init__(key, config, context)
        self._condition_trace: dict[str, Deque[TraceElement]] | None = None

    def set_condition_trace(self, trace: dict[str, Deque[TraceElement]]) -> None:
        """Set condition trace."""
        self._condition_trace = trace

    def as_dict(self) -> dict[str, Any]:
        """Return dictionary version of this AutomationTrace."""

        result = super().as_dict()

        condition_traces = {}

        if self._condition_trace:
            for key, trace_list in self._condition_trace.items():
                condition_traces[key] = [item.as_dict() for item in trace_list]
        result["condition_trace"] = condition_traces

        return result

    def as_short_dict(self) -> dict[str, Any]:
        """Return a brief dictionary version of this AutomationTrace."""

        result = super().as_short_dict()

        last_condition = None
        trigger = None

        if self._condition_trace:
            last_condition = list(self._condition_trace)[-1]
        if self._variables:
            trigger = self._variables.get("trigger", {}).get("description")

        result["trigger"] = trigger
        result["last_condition"] = last_condition

        return result


@contextmanager
def trace_automation(hass, item_id, config, context):
    """Trace action execution of automation with automation_id."""
    key = ("automation", item_id)
    trace = AutomationTrace(key, config, context)
    trace_id_set((key, trace.run_id))

    if key:
        traces = hass.data[DATA_TRACE]
        if key not in traces:
            traces[key] = LimitedSizeDict(size_limit=STORED_TRACES)
        traces[key][trace.run_id] = trace

    try:
        yield trace
    except Exception as ex:  # pylint: disable=broad-except
        if key:
            trace.set_error(ex)
        raise ex
    finally:
        if key:
            trace.finished()
