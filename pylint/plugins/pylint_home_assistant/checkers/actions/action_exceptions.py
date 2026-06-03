"""Checker for action handlers that don't raise HomeAssistantError.

The ``action-exceptions`` quality scale rule requires that action handlers
surface failures to the user as ``HomeAssistantError`` (or a subclass like
``ServiceValidationError``).

A handler satisfies the rule if either:

- It is wrapped in a decorator (decorators are the escape hatch for
  centralized error translation, e.g. ``@catch_lib_errors``), or
- Its body contains a ``raise`` of a ``HomeAssistantError`` subclass.

Anything else is flagged: a handler that calls into a library without a
``try/except`` (so a raw lib exception escapes), or one that catches a lib
exception but re-raises something other than ``HomeAssistantError``.

This complements ``home-assistant-action-swallowed-exception``: that
checker ensures exceptions aren't silently dropped; this one ensures the
exception type that escapes is one Home Assistant knows how to present.
"""

from collections.abc import Iterator

import astroid
from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.quality_scale import (
    quality_scale_rule_is_done_or_exempt,
)

from .helpers import ActionHandlers, collect_action_handlers
from .swallowed_exceptions import _is_action_handler

_HA_ERROR_QNAME = "homeassistant.exceptions.HomeAssistantError"


def _is_ha_error(exc: nodes.NodeNG) -> bool:
    """Return True if *exc* constructs a HomeAssistantError subclass."""
    target = exc.func if isinstance(exc, nodes.Call) else exc
    if not isinstance(target, (nodes.Name, nodes.Attribute)):
        return False
    try:
        for inferred in target.infer():
            if not isinstance(inferred, nodes.ClassDef):
                continue
            if inferred.qname() == _HA_ERROR_QNAME:
                return True
            try:
                for ancestor in inferred.ancestors():
                    if ancestor.qname() == _HA_ERROR_QNAME:
                        return True
            except astroid.exceptions.InferenceError:
                continue
    except astroid.exceptions.InferenceError:
        return False
    return False


def _iter_raises(body: list[nodes.NodeNG]) -> Iterator[nodes.Raise]:
    """Yield Raise nodes from a function body, not descending into nested defs."""
    for child in body:
        if isinstance(child, (nodes.FunctionDef, nodes.AsyncFunctionDef)):
            continue
        if isinstance(child, nodes.Raise):
            yield child
        for sub in getattr(child, "body", []) or []:
            yield from _iter_raises([sub])
        for sub in getattr(child, "orelse", []) or []:
            yield from _iter_raises([sub])
        for sub in getattr(child, "finalbody", []) or []:
            yield from _iter_raises([sub])
        for handler in getattr(child, "handlers", []) or []:
            yield from _iter_raises(handler.body)


def _iter_calls(body: list[nodes.NodeNG]) -> Iterator[nodes.Call]:
    """Yield Call nodes from a function body, not descending into nested defs."""
    for child in body:
        if isinstance(child, (nodes.FunctionDef, nodes.AsyncFunctionDef)):
            continue
        if isinstance(child, nodes.Call):
            yield child
        yield from _iter_calls(list(child.get_children()))


def _called_function_raises_ha_error(call: nodes.Call) -> bool:
    """Return True if the function being called raises HomeAssistantError.

    Only inspects one level deep — a helper that itself delegates further
    is not followed, to keep inference cost bounded and avoid recursion.
    """
    try:
        for inferred in call.func.infer():
            if not isinstance(inferred, (nodes.FunctionDef, nodes.AsyncFunctionDef)):
                continue
            for raise_node in _iter_raises(inferred.body):
                if raise_node.exc is None:
                    continue
                if _is_ha_error(raise_node.exc):
                    return True
    except astroid.exceptions.InferenceError:
        return False
    return False


def _raises_ha_error(body: list[nodes.NodeNG]) -> bool:
    """Return True if the body raises a HomeAssistantError subclass.

    Direct ``raise`` statements are checked first; if none qualify, calls
    in the body are inspected one level deep to detect helper methods
    (e.g., a custom ``_async_send_command``) that translate library
    errors into ``HomeAssistantError``.
    """
    for raise_node in _iter_raises(body):
        if raise_node.exc is None:
            # Bare re-raise — type unknown, doesn't satisfy the rule.
            continue
        if _is_ha_error(raise_node.exc):
            return True
    return any(_called_function_raises_ha_error(call) for call in _iter_calls(body))


class ActionExceptionsChecker(BaseChecker):
    """Checker for the action-exceptions quality scale rule."""

    name = "home_assistant_actions_exceptions"
    priority = -1
    msgs = {
        "W7423": (
            "Action handler '%s' should raise HomeAssistantError (or a "
            "subclass) so library failures are surfaced to the user, or "
            "be wrapped in a decorator that translates exceptions "
            "(integration claims the 'action-exceptions' quality scale "
            "rule as done/exempt)",
            "home-assistant-action-missing-ha-exception",
            "Used when an action handler (service handler or platform "
            "entity action like async_turn_on) neither raises a "
            "HomeAssistantError subclass nor is wrapped in a decorator, "
            "while the integration's quality_scale.yaml marks the "
            "'action-exceptions' rule as done or exempt. A raw library "
            "exception escaping the handler is shown to the user as an "
            "opaque traceback.",
        ),
    }
    options = ()

    _action_handlers: ActionHandlers
    _rule_active: bool

    def visit_module(self, node: nodes.Module) -> None:
        """Determine which action handlers to check for this module."""
        self._action_handlers = collect_action_handlers(node)
        self._rule_active = quality_scale_rule_is_done_or_exempt(
            node, "action-exceptions"
        )

    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        """Check action handlers raise HomeAssistantError or are decorated."""
        if not self._rule_active:
            return
        if not self._action_handlers.all_names:
            return
        if not _is_action_handler(node, self._action_handlers):
            return
        # Any decorator is treated as an escape hatch — it may wrap the
        # handler and translate exceptions centrally.
        if node.decorators and node.decorators.nodes:
            return
        if _raises_ha_error(node.body):
            return
        self.add_message(
            "home-assistant-action-missing-ha-exception",
            node=node,
            args=(node.name,),
        )

    visit_asyncfunctiondef = visit_functiondef


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(ActionExceptionsChecker(linter))
