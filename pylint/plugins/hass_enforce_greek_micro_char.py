"""Plugin for checking correct micro unicode card is used."""

from __future__ import annotations

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter


class HassEnforceGreekMicroCharChecker(BaseChecker):
    """Checker for micro char."""

    name = "hass-enforce-greek-micro-char"
    priority = -1
    msgs = {
        "W7452": (
            "Constants with the mico sign must be encoded as U+03BC (\u03bc), not as U+00B5 (\u00b5)",
            "hass-enforce-greek-micro-char",
            "According to [The Unicode Consortium](https://en.wikipedia.org/wiki/Unicode_Consortium), the Greek letter character is preferred [10].",
        ),
    }
    options = ()

    def visit_annassign(self, node: nodes.AnnAssign) -> None:
        """Check for sorted PLATFORMS const with type annotations."""
        self._do_micro_check(node.target, node)

    def visit_assign(self, node: nodes.Assign) -> None:
        """Check for sorted PLATFORMS const without type annotations."""
        for target in node.targets:
            self._do_micro_check(target, node)

    def _do_micro_check(
        self, target: nodes.NodeNG, node: nodes.Assign | nodes.AnnAssign
    ) -> None:
        """Check const assignment is not containing ANSI micro char."""
        if (
            isinstance(target, nodes.AssignName)
            and isinstance(node.value, nodes.Const)
            and isinstance(node.value.value, str)
            and "\u00b5" in node.value.value
        ):
            self.add_message(self.name, node=node)


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassEnforceGreekMicroCharChecker(linter))
