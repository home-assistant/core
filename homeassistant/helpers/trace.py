"""Helpers for script and condition tracing."""
from collections import deque
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Deque, Dict, Generator, List, Optional, Union, cast

from homeassistant.helpers.typing import TemplateVarsType
import homeassistant.util.dt as dt_util


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


# Context variables for tracing
# Current trace
trace_cv: ContextVar[Optional[Dict[str, Deque[TraceElement]]]] = ContextVar(
    "trace_cv", default=None
)
# Stack of TraceElements
trace_stack_cv: ContextVar[Optional[List[TraceElement]]] = ContextVar(
    "trace_stack_cv", default=None
)
# Current location in config tree
trace_path_stack_cv: ContextVar[Optional[List[str]]] = ContextVar(
    "trace_path_stack_cv", default=None
)


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


def trace_path_push(suffix: Union[str, List[str]]) -> int:
    """Go deeper in the config tree."""
    if isinstance(suffix, str):
        suffix = [suffix]
    for node in suffix:
        trace_stack_push(trace_path_stack_cv, node)
    return len(suffix)


def trace_path_pop(count: int) -> None:
    """Go n levels up in the config tree."""
    for _ in range(count):
        trace_stack_pop(trace_path_stack_cv)


def trace_path_get() -> str:
    """Return a string representing the current location in the config tree."""
    path = trace_path_stack_cv.get()
    if not path:
        return ""
    return "/".join(path)


def trace_append_element(
    trace_element: TraceElement,
    path: str,
    maxlen: Optional[int] = None,
) -> None:
    """Append a TraceElement to trace[path]."""
    trace = trace_cv.get()
    if trace is None:
        trace = {}
        trace_cv.set(trace)
    if path not in trace:
        trace[path] = deque(maxlen=maxlen)
    trace[path].append(trace_element)


def trace_get(clear: bool = True) -> Optional[Dict[str, Deque[TraceElement]]]:
    """Return the current trace."""
    if clear:
        trace_clear()
    return trace_cv.get()


def trace_clear() -> None:
    """Clear the trace."""
    trace_cv.set({})
    trace_stack_cv.set(None)
    trace_path_stack_cv.set(None)


def trace_set_result(**kwargs: Any) -> None:
    """Set the result of TraceElement at the top of the stack."""
    node = cast(TraceElement, trace_stack_top(trace_stack_cv))
    node.set_result(**kwargs)


@contextmanager
def trace_path(suffix: Union[str, List[str]]) -> Generator:
    """Go deeper in the config tree."""
    count = trace_path_push(suffix)
    try:
        yield
    finally:
        trace_path_pop(count)
