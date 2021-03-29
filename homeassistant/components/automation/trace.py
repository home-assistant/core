"""Trace support for automation."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Deque

from homeassistant.components.trace import ActionTrace, async_store_trace
from homeassistant.core import Context
from homeassistant.helpers.trace import TraceElement

# mypy: allow-untyped-calls, allow-untyped-defs
# mypy: no-check-untyped-defs, no-warn-return-any


class AutomationTrace(ActionTrace):
    """Container for automation trace."""

    def __init__(
        self,
        item_id: str,
        config: dict[str, Any],
        context: Context,
    ):
        """Container for automation trace."""
        key = ("automation", item_id)
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
def trace_automation(hass, automation_id, config, context):
    """Trace action execution of automation with automation_id."""
    trace = AutomationTrace(automation_id, config, context)
    async_store_trace(hass, trace)

    try:
        yield trace
    except Exception as ex:  # pylint: disable=broad-except
        if automation_id:
            trace.set_error(ex)
        raise ex
    finally:
        if automation_id:
            trace.finished()
