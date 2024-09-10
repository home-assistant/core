"""Plugin for checking if coordinator is in its own module."""

from __future__ import annotations

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter


class HassEnforceClassModule(BaseChecker):
    """Checker for coordinators own module."""

    name = "hass_enforce_class_module"
    priority = -1
    msgs = {
        "C7461": (
            "Derived data update coordinator is recommended to be placed in the 'coordinator' module",
            "hass-enforce-class-module",
            "Used when derived data update coordinator should be placed in its own module.",
        ),
    }

    def visit_classdef(self, node: nodes.ClassDef) -> None:
        """Check if derived data update coordinator is placed in its own module."""
        root_name = node.root().name

        # we only want to check component update coordinators
        if not root_name.startswith("homeassistant.components"):
            return

        is_coordinator_module = root_name.endswith(".coordinator")
        for ancestor in node.ancestors():
            if ancestor.name == "DataUpdateCoordinator" and not is_coordinator_module:
                self.add_message("hass-enforce-class-module", node=node)
                return


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassEnforceClassModule(linter))
