"""Helpers for script and condition tracing."""
from __future__ import annotations

from collections import deque
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from typing import Any, Callable, cast

from homeassistant.helpers.typing import TemplateVarsType
import homeassistant.util.dt as dt_util


class TraceElement:
    """Container for trace data."""

    def __init__(self, variables: TemplateVarsType, path: str) -> None:
        """Container for trace data."""
        self._child_key: tuple[str, str] | None = None
        self._child_run_id: str | None = None
        self._error: Exception | None = None
        self.path: str = path
        self._result: dict | None = None
        self.reuse_by_child = False
        self._timestamp = dt_util.utcnow()

        if variables is None:
            variables = {}
        last_variables = variables_cv.get() or {}
        variables_cv.set(dict(variables))
        changed_variables = {
            key: value
            for key, value in variables.items()
            if key not in last_variables or last_variables[key] != value
        }
        self._variables = changed_variables

    def __repr__(self) -> str:
        """Container for trace data."""
        return str(self.as_dict())

    def set_child_id(self, child_key: tuple[str, str], child_run_id: str) -> None:
        """Set trace id of a nested script run."""
        self._child_key = child_key
        self._child_run_id = child_run_id

    def set_error(self, ex: Exception) -> None:
        """Set error."""
        self._error = ex

    def set_result(self, **kwargs: Any) -> None:
        """Set result."""
        self._result = {**kwargs}

    def update_result(self, **kwargs: Any) -> None:
        """Set result."""
        old_result = self._result or {}
        self._result = {**old_result, **kwargs}

    def as_dict(self) -> dict[str, Any]:
        """Return dictionary version of this TraceElement."""
        result: dict[str, Any] = {"path": self.path, "timestamp": self._timestamp}
        if self._child_key is not None:
            result["child_id"] = {
                "domain": self._child_key[0],
                "item_id": self._child_key[1],
                "run_id": str(self._child_run_id),
            }
        if self._variables:
            result["changed_variables"] = self._variables
        if self._error is not None:
            result["error"] = str(self._error)
        if self._result is not None:
            result["result"] = self._result
        return result


# Context variables for tracing
# Current trace
trace_cv: ContextVar[dict[str, deque[TraceElement]] | None] = ContextVar(
    "trace_cv", default=None
)
# Stack of TraceElements
trace_stack_cv: ContextVar[list[TraceElement] | None] = ContextVar(
    "trace_stack_cv", default=None
)
# Current location in config tree
trace_path_stack_cv: ContextVar[list[str] | None] = ContextVar(
    "trace_path_stack_cv", default=None
)
# Copy of last variables
variables_cv: ContextVar[Any | None] = ContextVar("variables_cv", default=None)
# (domain, item_id) + Run ID
trace_id_cv: ContextVar[tuple[tuple[str, str], str] | None] = ContextVar(
    "trace_id_cv", default=None
)
# Reason for stopped script execution
script_execution_cv: ContextVar[StopReason | None] = ContextVar(
    "script_execution_cv", default=None
)


def trace_id_set(trace_id: tuple[tuple[str, str], str]) -> None:
    """Set id of the current trace."""
    trace_id_cv.set(trace_id)


def trace_id_get() -> tuple[tuple[str, str], str] | None:
    """Get id if the current trace."""
    return trace_id_cv.get()


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


def trace_stack_top(trace_stack_var: ContextVar) -> Any | None:
    """Return the element at the top of a trace stack."""
    trace_stack = trace_stack_var.get()
    return trace_stack[-1] if trace_stack else None


def trace_path_push(suffix: str | list[str]) -> int:
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
    maxlen: int | None = None,
) -> None:
    """Append a TraceElement to trace[path]."""
    path = trace_element.path
    trace = trace_cv.get()
    if trace is None:
        trace = {}
        trace_cv.set(trace)
    if path not in trace:
        trace[path] = deque(maxlen=maxlen)
    trace[path].append(trace_element)


def trace_get(clear: bool = True) -> dict[str, deque[TraceElement]] | None:
    """Return the current trace."""
    if clear:
        trace_clear()
    return trace_cv.get()


def trace_clear() -> None:
    """Clear the trace."""
    trace_cv.set({})
    trace_stack_cv.set(None)
    trace_path_stack_cv.set(None)
    variables_cv.set(None)
    script_execution_cv.set(StopReason())


def trace_set_child_id(child_key: tuple[str, str], child_run_id: str) -> None:
    """Set child trace_id of TraceElement at the top of the stack."""
    node = cast(TraceElement, trace_stack_top(trace_stack_cv))
    if node:
        node.set_child_id(child_key, child_run_id)


def trace_set_result(**kwargs: Any) -> None:
    """Set the result of TraceElement at the top of the stack."""
    node = cast(TraceElement, trace_stack_top(trace_stack_cv))
    node.set_result(**kwargs)


def trace_update_result(**kwargs: Any) -> None:
    """Update the result of TraceElement at the top of the stack."""
    node = cast(TraceElement, trace_stack_top(trace_stack_cv))
    node.update_result(**kwargs)


class StopReason:
    """Mutable container class for script_execution."""

    script_execution: str | None = None


def script_execution_set(reason: str) -> None:
    """Set stop reason."""
    data = script_execution_cv.get()
    if data is None:
        return
    data.script_execution = reason


def script_execution_get() -> str | None:
    """Return the current trace."""
    data = script_execution_cv.get()
    if data is None:
        return None
    return data.script_execution


@contextmanager
def trace_path(suffix: str | list[str]) -> Generator:
    """Go deeper in the config tree.

    Can not be used as a decorator on couroutine functions.
    """
    count = trace_path_push(suffix)
    try:
        yield
    finally:
        trace_path_pop(count)


def async_trace_path(suffix: str | list[str]) -> Callable:
    """Go deeper in the config tree.

    To be used as a decorator on coroutine functions.
    """

    def _trace_path_decorator(func: Callable) -> Callable:
        """Decorate a coroutine function."""

        @wraps(func)
        async def async_wrapper(*args: Any) -> None:
            """Catch and log exception."""
            with trace_path(suffix):
                await func(*args)

        return async_wrapper

    return _trace_path_decorator
