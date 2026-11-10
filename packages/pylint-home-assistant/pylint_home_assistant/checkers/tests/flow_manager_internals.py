"""Checker for tests that reach into the config entry flow managers.

Integration tests should drive a flow the way the frontend does: start it
with ``async_init``, answer its steps with ``async_configure`` and assert on
the results that come back. Reaching into the private state of
``hass.config_entries.flow``, ``hass.config_entries.options`` or
``hass.config_entries.subentries`` (``_progress``,
``_handler_progress_index``, ``_async_remove_flow_progress`` and so on) to
grab the flow handler or change what is in progress couples the test to
implementation details of the flow manager and the handler, and skips the
behavior a user would actually see.

``W7464`` (``home-assistant-tests-flow-manager-internals``)
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import parse_module

_FLOW_MANAGERS = frozenset({"flow", "options", "subentries"})


def _is_flow_manager(node: nodes.NodeNG) -> bool:
    """Return True if *node* is ``<x>.config_entries.<flow manager>``."""
    match node:
        case nodes.Attribute(
            attrname=attrname,
            expr=nodes.Attribute(attrname="config_entries"),
        ) if attrname in _FLOW_MANAGERS:
            return True
    return False


def _is_flow_manager_alias(node: nodes.Name) -> bool:
    """Return True if *node* is a local name bound to a flow manager."""
    _, assignments = node.lookup(node.name)
    for assignment in assignments:
        match assignment:
            case nodes.AssignName(
                parent=nodes.Assign(value=value) | nodes.AnnAssign(value=value)
            ) if _is_flow_manager(value):
                return True
    return False


class FlowManagerInternalsChecker(BaseChecker):
    """Checker for tests that access private flow manager attributes."""

    name = "home_assistant_tests_flow_manager_internals"
    priority = -1
    msgs = {
        "W7464": (
            "Do not access `%s` of the flow manager in tests; drive the flow "
            "with `async_init` and `async_configure` and assert on the results",
            "home-assistant-tests-flow-manager-internals",
            "Used when an integration test accesses a private attribute of "
            "`hass.config_entries.flow`, `hass.config_entries.options` or "
            "`hass.config_entries.subentries`, for example to get the flow "
            "handler out of `_progress`. Tests should only use the public "
            "flow manager API.",
        ),
    }
    options = ()

    _in_integration_test: bool = False

    def visit_module(self, node: nodes.Module) -> None:
        """Track whether we are in an integration test module."""
        self._in_integration_test = node.name.startswith("tests.") and (
            parse_module(node.name, include_test=True) is not None
        )

    def visit_attribute(self, node: nodes.Attribute) -> None:
        """Flag private attribute access on a flow manager."""
        if not self._in_integration_test:
            return
        attrname = node.attrname
        if not attrname.startswith("_") or attrname.startswith("__"):
            return
        expr = node.expr
        if _is_flow_manager(expr) or (
            isinstance(expr, nodes.Name) and _is_flow_manager_alias(expr)
        ):
            self.add_message(
                "home-assistant-tests-flow-manager-internals",
                node=node,
                args=(attrname,),
            )

    visit_assignattr = visit_attribute
    visit_delattr = visit_attribute


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(FlowManagerInternalsChecker(linter))
