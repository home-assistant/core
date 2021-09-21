"""Plugin for return statements."""
from __future__ import annotations

from astroid import AsyncFunctionDef, Const, FunctionDef, Return
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
            "Remove explicit None in return",
            "hass-return-none",
            "Used when function returns nothing but has explicit 'return None'",
        ),
    }
    options = ()

    def visit_return(self, node: Return) -> None:
        """Called when a Return node is visited."""
        if isinstance(node.value, Const) and node.value.value is None:
            # Find enclosing function
            parent = node.parent
            while (
                parent is not None
                and not isinstance(parent, FunctionDef)
                and not isinstance(parent, AsyncFunctionDef)
            ):
                parent = parent.parent
            if parent is None:
                return
            if isinstance(parent.returns, Const) and parent.returns.value is None:
                self.add_message("hass-return-none", node=node)


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassReturnFormatChecker(linter))
