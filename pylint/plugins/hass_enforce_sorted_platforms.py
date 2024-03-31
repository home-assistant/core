"""Plugin for checking sorted platforms list."""

from __future__ import annotations

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter


class HassEnforceSortedPlatformsChecker(BaseChecker):
    """Checker for sorted platforms list."""

    name = "hass_enforce_sorted_platforms"
    priority = -1
    msgs = {
        "W7451": (
            "Platforms must be sorted alphabetically",
            "hass-enforce-sorted-platforms",
            "Used when PLATFORMS should be sorted alphabetically.",
        ),
    }
    options = ()

    def visit_annassign(self, node: nodes.AnnAssign) -> None:
        """Check for sorted PLATFORMS const with type annotations."""
        self._do_sorted_check(node.target, node)

    def visit_assign(self, node: nodes.Assign) -> None:
        """Check for sorted PLATFORMS const without type annotations."""
        for target in node.targets:
            self._do_sorted_check(target, node)

    def _do_sorted_check(
        self, target: nodes.NodeNG, node: nodes.Assign | nodes.AnnAssign
    ) -> None:
        """Check for sorted PLATFORMS const."""
        if (
            isinstance(target, nodes.AssignName)
            and target.name == "PLATFORMS"
            and isinstance(node.value, nodes.List)
        ):
            platforms = [v.as_string() for v in node.value.elts]
            sorted_platforms = sorted(platforms)
            if platforms != sorted_platforms:
                self.add_message("hass-enforce-sorted-platforms", node=node)


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassEnforceSortedPlatformsChecker(linter))
