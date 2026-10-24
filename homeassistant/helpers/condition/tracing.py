"""Tracing condition helpers."""

from typing import Any

from homeassistant.helpers.trace import (
    TraceElement,
    trace_append_element,
    trace_path_get,
    trace_stack_cv,
    trace_stack_pop,
    trace_stack_push,
    trace_stack_top,
)
from homeassistant.helpers.typing import TemplateVarsType


class trace_condition:
    """Trace condition evaluation."""

    __slots__ = ("_should_pop", "_trace_element", "_variables")

    _should_pop: bool
    _trace_element: TraceElement

    def __init__(self, variables: TemplateVarsType) -> None:
        """Store the variables for the trace element."""
        self._variables = variables

    def __enter__(self) -> TraceElement:
        """Start tracing the condition evaluation."""
        should_pop = True
        trace_element = trace_stack_top(trace_stack_cv)
        if trace_element and trace_element.reuse_by_child:
            should_pop = False
            trace_element.reuse_by_child = False
        else:
            trace_element = condition_trace_append(self._variables, trace_path_get())
            trace_stack_push(trace_stack_cv, trace_element)
        self._should_pop = should_pop
        self._trace_element = trace_element
        return trace_element

    def __exit__(
        self, exc_type: object, exc_val: BaseException | None, exc_tb: object
    ) -> None:
        """Finish tracing the condition evaluation."""
        try:
            if exc_val is not None and isinstance(exc_val, Exception):
                self._trace_element.set_error(exc_val)
        finally:
            if self._should_pop:
                trace_stack_pop(trace_stack_cv)


def condition_trace_append(variables: TemplateVarsType, path: str) -> TraceElement:
    """Append a TraceElement to trace[path]."""
    trace_element = TraceElement(variables, path)
    trace_append_element(trace_element)
    return trace_element


def condition_trace_set_result(result: bool, **kwargs: Any) -> None:
    """Set the result of TraceElement at the top of the stack."""
    node = trace_stack_top(trace_stack_cv)

    # The condition function may be called directly, in which case tracing
    # is not setup
    if not node:
        return

    node.set_result(result=result, **kwargs)


def condition_trace_update_result(**kwargs: Any) -> None:
    """Update the result of TraceElement at the top of the stack."""
    node = trace_stack_top(trace_stack_cv)

    # The condition function may be called directly, in which case tracing
    # is not setup
    if not node:
        return
    node.update_result(**kwargs)
