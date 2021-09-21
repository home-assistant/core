"""Plugin for return statements."""
from __future__ import annotations

from astroid import Const, FunctionDef, Return
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

    def __init__(self, linter: PyLinter | None = None) -> None:
        super().__init__(linter)
        self.returns_none = False

    def visit_functiondef(self, node: FunctionDef) -> None:
        """Called when a FunctionDef node is visited."""

        # Check that return type is specified and it is "None".
        self.returns_none = (
            isinstance(node.returns, Const) and node.returns.value is None
        )

    def visit_return(self, node: Return) -> None:
        """Called when a Return node is visited."""
        if (
            self.returns_none
            and isinstance(node.value, Const)
            and node.value.value is None
        ):
            self.add_message("hass-return-none", node=node)


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassReturnFormatChecker(linter))
