"""Plugin to check decorators."""

from __future__ import annotations

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter


class HassDecoratorChecker(BaseChecker):
    """Checker for decorators."""

    name = "hass_decorator"
    priority = -1
    msgs = {
        "W7471": (
            "A coroutine function should not be decorated with @callback",
            "hass-async-callback-decorator",
            "Used when a coroutine function has an invalid @callback decorator",
        ),
    }

    def visit_asyncfunctiondef(self, node: nodes.AsyncFunctionDef) -> None:
        """Apply checks on an AsyncFunctionDef node."""
        if (
            decoratornames := node.decoratornames()
        ) and "homeassistant.core.callback" in decoratornames:
            self.add_message("hass-async-callback-decorator", node=node)


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassDecoratorChecker(linter))
