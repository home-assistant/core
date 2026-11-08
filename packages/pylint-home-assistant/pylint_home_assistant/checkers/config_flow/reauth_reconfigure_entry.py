"""Checker for config entry lookups in reauth and reconfigure steps.

Reauth and reconfigure steps should use ``self._get_reauth_entry()`` and
``self._get_reconfigure_entry()`` instead of looking up the config entry
from ``self.context["entry_id"]``.
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.ast_utils import get_flow_type

LOOKUP_METHODS = {"async_get_entry", "async_get_known_entry"}

STEP_HELPERS = {
    "async_step_reauth": "_get_reauth_entry",
    "async_step_reconfigure": "_get_reconfigure_entry",
}


def _is_self_context(node: nodes.NodeNG) -> bool:
    """Return True if node is ``self.context``."""
    match node:
        case nodes.Attribute(attrname="context", expr=nodes.Name(name="self")):
            return True
    return False


def _is_context_entry_id(node: nodes.NodeNG) -> bool:
    """Return True if node reads ``entry_id`` from ``self.context``."""
    match node:
        case nodes.Subscript(value=value, slice=nodes.Const(value="entry_id")):
            return _is_self_context(value)
        case nodes.Call(
            func=nodes.Attribute(attrname="get", expr=expr),
            args=[nodes.Const(value="entry_id"), *_],
        ):
            return _is_self_context(expr)
    return False


def _refers_to_context_entry_id(node: nodes.NodeNG) -> bool:
    """Return True if node is, or is a local name assigned from, the entry_id."""
    if _is_context_entry_id(node):
        return True
    if not isinstance(node, nodes.Name):
        return False
    _, assignments = node.lookup(node.name)
    return any(
        isinstance(assign_name.parent, nodes.Assign)
        and _is_context_entry_id(assign_name.parent.value)
        for assign_name in assignments
    )


class HassEnforceReauthReconfigureEntryHelperChecker(BaseChecker):
    """Checker for manual config entry lookups in reauth/reconfigure steps."""

    name = "home_assistant_reauth_reconfigure_entry_helper"
    priority = -1
    msgs = {
        "W7464": (
            'Use `self.%s()` instead of looking up the config entry from `self.context["entry_id"]`',
            "home-assistant-use-reauth-reconfigure-entry-helper",
            "Used when a reauth or reconfigure step of a config flow looks up "
            "its config entry from the flow context instead of using "
            "`self._get_reauth_entry()` or `self._get_reconfigure_entry()`.",
        ),
    }
    options = ()

    def visit_call(self, node: nodes.Call) -> None:
        """Check config entry lookups."""
        if not (
            isinstance(node.func, nodes.Attribute)
            and node.func.attrname in LOOKUP_METHODS
            and node.args
            and _refers_to_context_entry_id(node.args[0])
        ):
            return

        function = node.scope()
        if not isinstance(function, nodes.FunctionDef):
            return
        helper = next(
            (
                helper
                for prefix, helper in STEP_HELPERS.items()
                if function.name.startswith(prefix)
            ),
            None,
        )
        if helper is None:
            return

        class_node = function.parent
        if not isinstance(class_node, nodes.ClassDef) or (
            get_flow_type(class_node) != "config"
        ):
            return

        self.add_message(
            "home-assistant-use-reauth-reconfigure-entry-helper",
            node=node,
            args=(helper,),
        )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassEnforceReauthReconfigureEntryHelperChecker(linter))
