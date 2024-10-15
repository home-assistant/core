"""Plugin for checking if the platforms list is sorted alphabetically."""

from __future__ import annotations

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter


class HassEnforceSortedPlatformsChecker(BaseChecker):
    """Checker to ensure that the platforms list is sorted alphabetically."""

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
        """Check for sorted PLATFORMS constant with type annotations."""
        self._check_sorted_platforms(node.target, node)

    def visit_assign(self, node: nodes.Assign) -> None:
        """Check for sorted PLATFORMS constant without type annotations."""
        for target in node.targets:
            self._check_sorted_platforms(target, node)

    def _check_sorted_platforms(
        self, target: nodes.NodeNG, node: nodes.Assign | nodes.AnnAssign
    ) -> None:
        """Check if the PLATFORMS list is sorted alphabetically."""
        if (
            isinstance(target, nodes.AssignName)
            and target.name == "PLATFORMS"
            and isinstance(node.value, nodes.List)
        ):
            platforms = [value.as_string() for value in node.value.elts]
            sorted_platforms = sorted(platforms)
            if platforms != sorted_platforms:
                self.add_message("hass-enforce-sorted-platforms", node=node)

def register(linter: PyLinter) -> None:
    """Register the checker with the pylint linter."""
    linter.register_checker(HassEnforceSortedPlatformsChecker(linter))
