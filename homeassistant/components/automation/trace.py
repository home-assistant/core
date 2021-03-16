"""Trace support for automation."""
from collections import OrderedDict
from contextlib import contextmanager
import datetime as dt
from datetime import timedelta
from itertools import count
import logging
from typing import Any, Awaitable, Callable, Deque, Dict, Optional

from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.helpers.json import JSONEncoder as HAJSONEncoder
from homeassistant.helpers.trace import TraceElement, trace_id_set
from homeassistant.helpers.typing import TemplateVarsType
from homeassistant.util import dt as dt_util

DATA_AUTOMATION_TRACE = "automation_trace"
STORED_TRACES = 5  # Stored traces per automation

_LOGGER = logging.getLogger(__name__)
AutomationActionType = Callable[[HomeAssistant, TemplateVarsType], Awaitable[None]]

# mypy: allow-untyped-calls, allow-untyped-defs
# mypy: no-check-untyped-defs, no-warn-return-any


class AutomationTrace:
    """Container for automation trace."""

    _run_ids = count(0)

    def __init__(
        self,
        unique_id: Optional[str],
        config: Dict[str, Any],
        context: Context,
    ):
        """Container for automation trace."""
        self._action_trace: Optional[Dict[str, Deque[TraceElement]]] = None
        self._condition_trace: Optional[Dict[str, Deque[TraceElement]]] = None
        self._config: Dict[str, Any] = config
        self._context: Context = context
        self._error: Optional[Exception] = None
        self._state: str = "running"
        self.run_id: str = str(next(self._run_ids))
        self._timestamp_finish: Optional[dt.datetime] = None
        self._timestamp_start: dt.datetime = dt_util.utcnow()
        self._unique_id: Optional[str] = unique_id
        self._variables: Optional[Dict[str, Any]] = None

    def set_action_trace(self, trace: Dict[str, Deque[TraceElement]]) -> None:
        """Set action trace."""
        self._action_trace = trace

    def set_condition_trace(self, trace: Dict[str, Deque[TraceElement]]) -> None:
        """Set condition trace."""
        self._condition_trace = trace

    def set_error(self, ex: Exception) -> None:
        """Set error."""
        self._error = ex

    def set_variables(self, variables: Dict[str, Any]) -> None:
        """Set variables."""
        self._variables = variables

    def finished(self) -> None:
        """Set finish time."""
        self._timestamp_finish = dt_util.utcnow()
        self._state = "stopped"

    def as_dict(self) -> Dict[str, Any]:
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
                "context": self._context,
                "variables": self._variables,
            }
        )
        if self._error is not None:
            result["error"] = str(self._error)
        return result

    def as_short_dict(self) -> Dict[str, Any]:
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


class LimitedSizeDict(OrderedDict):
    """OrderedDict limited in size."""

    def __init__(self, *args, **kwds):
        """Initialize OrderedDict limited in size."""
        self.size_limit = kwds.pop("size_limit", None)
        OrderedDict.__init__(self, *args, **kwds)
        self._check_size_limit()

    def __setitem__(self, key, value):
        """Set item and check dict size."""
        OrderedDict.__setitem__(self, key, value)
        self._check_size_limit()

    def _check_size_limit(self):
        """Check dict size and evict items in FIFO order if needed."""
        if self.size_limit is not None:
            while len(self) > self.size_limit:
                self.popitem(last=False)


@contextmanager
def trace_automation(hass, unique_id, config, context):
    """Trace action execution of automation with automation_id."""
    automation_trace = AutomationTrace(unique_id, config, context)
    trace_id_set((unique_id, automation_trace.run_id))

    if unique_id:
        automation_traces = hass.data[DATA_AUTOMATION_TRACE]
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


@callback
def get_debug_trace(hass, automation_id, run_id):
    """Return a serializable debug trace."""
    return hass.data[DATA_AUTOMATION_TRACE][automation_id][run_id]


@callback
def get_debug_traces_for_automation(hass, automation_id, summary=False):
    """Return a serializable list of debug traces for an automation."""
    traces = []

    for trace in hass.data[DATA_AUTOMATION_TRACE].get(automation_id, {}).values():
        if summary:
            traces.append(trace.as_short_dict())
        else:
            traces.append(trace.as_dict())

    return traces


@callback
def get_debug_traces(hass, summary=False):
    """Return a serializable list of debug traces."""
    traces = []

    for automation_id in hass.data[DATA_AUTOMATION_TRACE]:
        traces.extend(get_debug_traces_for_automation(hass, automation_id, summary))

    return traces


class TraceJSONEncoder(HAJSONEncoder):
    """JSONEncoder that supports Home Assistant objects and falls back to repr(o)."""

    def default(self, o: Any) -> Any:
        """Convert certain objects.

        Fall back to repr(o).
        """
        if isinstance(o, timedelta):
            return {"__type": str(type(o)), "total_seconds": o.total_seconds()}
        try:
            return super().default(o)
        except TypeError:
            return {"__type": str(type(o)), "repr": repr(o)}
