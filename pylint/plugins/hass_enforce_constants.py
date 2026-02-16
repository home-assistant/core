"""Plugin to enforce type hints on specific functions."""

from __future__ import annotations

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter


class HassEnforceConstantsChecker(BaseChecker):
    """Checker for use of constants."""

    name = "hass_enforce_constants"
    priority = -1
    msgs = {
        "W7491": (
            "Argument %s should be a DOMAIN constant in %s",
            "hass-argument-domain-constant",
            "Used when method argument should be a DOMAIN constant.",
        ),
    }

    _in_test_module: bool

    def visit_module(self, node: nodes.Module) -> None:
        """Visit Module node."""
        self._in_test_module = node.name.startswith("tests.")

    def visit_call(self, node: nodes.Call) -> None:
        """Visit Call node."""
        if not self._in_test_module:
            return

        if isinstance(node.func, nodes.Name):
            if node.func.name == "async_setup_component":
                self._ensure_domain_argument(node, arg_position=1, kwarg_name="domain")

    def _ensure_domain_argument(
        self, call_node: nodes.Call, *, arg_position: int, kwarg_name: str
    ) -> None:

        if len(call_node.args) > arg_position:
            self._ensure_domain_argument_node(call_node, call_node.args[arg_position])

        for keyword in call_node.keywords:
            if keyword.arg == kwarg_name:
                self._ensure_domain_argument_node(call_node, keyword.value)
                return

    def _ensure_domain_argument_node(
        self, call_node: nodes.Call, arg_node: nodes.Argument | nodes.Keyword
    ) -> None:
        if isinstance(arg_node, nodes.Attribute) and arg_node.attrname.endswith(
            "DOMAIN"
        ):
            # component.***DOMAIN attribute constants are allowed
            return
        if isinstance(arg_node, nodes.Const):
            # Allow string literals
            return
        if isinstance(arg_node, nodes.Name) and arg_node.name.endswith("DOMAIN"):
            # ***DOMAIN constants are allowed
            return

        self.add_message(
            "hass-argument-domain-constant",
            node=arg_node,
            args=(arg_node.as_string(), call_node.func.as_string()),
        )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassEnforceConstantsChecker(linter))
