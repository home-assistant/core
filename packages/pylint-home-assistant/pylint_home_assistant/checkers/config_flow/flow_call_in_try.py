"""Checker for flow results and unique ID handling inside a ``try`` block.

A ``try`` block in a flow step should only contain the code that can raise the
errors it catches, such as the calls to the device or service. Creating the
entry, showing a form and handling the unique ID belong after it, in ``else:``
or after the ``try`` statement. The unique ID helpers raise ``AbortFlow``,
which a broad ``except Exception`` swallows and reports as an unknown error.

``W7457`` (``home-assistant-flow-call-in-try``)
"""

from collections.abc import Iterator

import astroid
from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.ast_utils import extended_ancestors
from pylint_home_assistant.helpers.module_info import is_integration_module

_ABORT_FLOW_QNAME = "homeassistant.data_entry_flow.AbortFlow"
_FLOW_HANDLER_QNAME = "homeassistant.data_entry_flow.FlowHandler"
_FLOW_METHODS = frozenset(
    {
        "_abort_if_unique_id_configured",
        "_abort_if_unique_id_mismatch",
        "_async_abort_entries_match",
        "_async_handle_discovery_without_unique_id",
        "async_abort",
        "async_create_entry",
        "async_external_step",
        "async_external_step_done",
        "async_set_unique_id",
        "async_show_form",
        "async_show_menu",
        "async_show_progress",
        "async_show_progress_done",
        "async_update_and_abort",
        "async_update_reload_and_abort",
    }
)


def _is_flow_handler(class_node: nodes.ClassDef) -> bool:
    """Return True if the class is a flow handler."""
    return any(
        ancestor.qname() == _FLOW_HANDLER_QNAME
        for ancestor in extended_ancestors(class_node)
    )


def _catches_abort_flow(node: nodes.Try) -> bool:
    """Return True if a handler of the ``try`` statement catches ``AbortFlow``."""
    for handler in node.handlers:
        if handler.type is None:
            continue
        exception_types = (
            handler.type.elts
            if isinstance(handler.type, nodes.Tuple)
            else [handler.type]
        )
        for exception_type in exception_types:
            try:
                inferred = list(exception_type.infer())
            except astroid.exceptions.InferenceError:
                continue
            if any(
                isinstance(item, nodes.ClassDef) and item.qname() == _ABORT_FLOW_QNAME
                for item in inferred
            ):
                return True
    return False


def _flow_calls(node: nodes.NodeNG) -> Iterator[nodes.Call]:
    """Yield the flow method calls on ``self`` in *node*.

    Calls in nested functions and classes run later, outside the ``try``
    block, so they are skipped. The body of a nested ``try`` statement with
    handlers is checked when that statement is visited, unless it catches
    ``AbortFlow`` itself: then its calls are still inside this ``try`` block.
    """
    if isinstance(node, (nodes.FunctionDef, nodes.Lambda, nodes.ClassDef)):
        return
    match node:
        case nodes.Call(
            func=nodes.Attribute(attrname=attrname, expr=nodes.Name(name="self"))
        ) if attrname in _FLOW_METHODS:
            yield node
    children = (
        (*node.handlers, *node.orelse, *node.finalbody)
        if isinstance(node, nodes.Try)
        and node.handlers
        and not _catches_abort_flow(node)
        else node.get_children()
    )
    for child in children:
        yield from _flow_calls(child)


class FlowCallInTryChecker(BaseChecker):
    """Checker for flow calls inside a ``try`` block."""

    name = "home_assistant_flow_call_in_try"
    priority = -1
    msgs = {
        "W7457": (
            (
                "Move `self.%s()` out of the `try` block, for example to "
                "`else:`, only keep code that can raise the caught errors in `try`"
            ),
            "home-assistant-flow-call-in-try",
            (
                "Used when a flow creates an entry, shows a form, aborts or "
                "handles the unique ID inside a `try` block with `except` "
                "handlers. Those calls don't raise the errors the handlers "
                "catch, and a broad handler swallows the `AbortFlow` raised by "
                "the unique ID helpers."
            ),
        ),
    }
    options = ()

    def visit_try(self, node: nodes.Try) -> None:
        """Check the body of ``try`` statements with ``except`` handlers."""
        if not node.handlers or not is_integration_module(node.root().name):
            return
        calls = [call for statement in node.body for call in _flow_calls(statement)]
        if not calls or _catches_abort_flow(node):
            return
        class_node = node.scope().parent
        if not isinstance(class_node, nodes.ClassDef) or not _is_flow_handler(
            class_node
        ):
            return
        for call in calls:
            self.add_message(
                "home-assistant-flow-call-in-try",
                node=call,
                args=(call.func.attrname,),
            )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(FlowCallInTryChecker(linter))
