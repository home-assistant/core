"""Helpers for script and condition tracing."""
from collections import deque
from contextvars import ContextVar
from typing import Any, Dict, Optional

from homeassistant.helpers.typing import TemplateVarsType
import homeassistant.util.dt as dt_util


def trace_stack_push(trace_stack_var: ContextVar, node: Any) -> None:
    """Push an element to the top of a trace stack."""
    trace_stack = trace_stack_var.get()
    if trace_stack is None:
        trace_stack = []
        trace_stack_var.set(trace_stack)
    trace_stack.append(node)


def trace_stack_pop(trace_stack_var: ContextVar) -> None:
    """Remove the top element from a trace stack."""
    trace_stack = trace_stack_var.get()
    trace_stack.pop()


def trace_stack_top(trace_stack_var: ContextVar) -> Optional[Any]:
    """Return the element at the top of a trace stack."""
    trace_stack = trace_stack_var.get()
    return trace_stack[-1] if trace_stack else None


class TraceElement:
    """Container for trace data."""

    def __init__(self, variables: TemplateVarsType):
        """Container for trace data."""
        self._error: Optional[Exception] = None
        self._result: Optional[dict] = None
        self._timestamp = dt_util.utcnow()
        self._variables = variables

    def __repr__(self) -> str:
        """Container for trace data."""
        return str(self.as_dict())

    def set_error(self, ex: Exception) -> None:
        """Set error."""
        self._error = ex

    def set_result(self, **kwargs: Any) -> None:
        """Set result."""
        self._result = {**kwargs}

    def as_dict(self) -> Dict[str, Any]:
        """Return dictionary version of this TraceElement."""
        result: Dict[str, Any] = {"timestamp": self._timestamp}
        # Commented out because we get too many copies of the same data
        # result["variables"] = self._variables
        if self._error is not None:
            result["error"] = str(self._error)
        if self._result is not None:
            result["result"] = self._result
        return result


def trace_append_element(
    trace_var: ContextVar,
    trace_element: TraceElement,
    path: str,
    maxlen: Optional[int] = None,
) -> None:
    """Append a TraceElement to trace[path]."""
    trace = trace_var.get()
    if trace is None:
        trace_var.set({})
        trace = trace_var.get()
    if path not in trace:
        trace[path] = deque(maxlen=maxlen)
    trace[path].append(trace_element)
