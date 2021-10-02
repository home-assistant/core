"""Plugin for return statements."""
from __future__ import annotations

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.interfaces import IAstroidChecker
from pylint.lint import PyLinter


class HassReturnFormatChecker(BaseChecker):  # type: ignore[misc]
    """Checker for return statements."""

    __implements__ = IAstroidChecker

    name = "hass_return"
    priority = -1
    msgs = {
        "W0016": (
            "Function annotated with return type 'None' returns value. "
            "Consider changing function return type or removing return value.",
            "hass-return-none",
            "Used when function returns some value while annotated with '-> None'",
        ),
    }
    options = ()

    def visit_return(self, node: nodes.Return) -> None:
        """Called when a Return node is visited."""
        if node.value is None:
            return
        # Find enclosing function
        parent = node.parent
        while (
            parent is not None
            and not isinstance(parent, nodes.FunctionDef)
            and not isinstance(parent, nodes.AsyncFunctionDef)
        ):
            parent = parent.parent
        if parent is None:
            return
        if isinstance(parent.returns, nodes.Const) and parent.returns.value is None:
            self.add_message("hass-return-none", node=node)


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassReturnFormatChecker(linter))
