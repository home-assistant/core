"""Plugin for checking async_add_entities not using list comprehensions."""
from __future__ import annotations

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter


class HassEnforceNonListComprehensionsChecker(BaseChecker):
    """Checker for async_add_entities not using list comprehensions."""

    name = "hass_enforce_non_list_comprehensions"
    priority = -1
    msgs = {
        "W7461": (
            "Call to async_add_entities should not use list comprehensions. "
            "Unwrap and use the generator expression directly.",
            "hass-enforce-non-list-comprehensions",
            "Used when async_add_entities should not use list comprehensions.",
        ),
    }
    options = ()

    def visit_call(self, node: nodes.Call) -> None:
        """Check if async_add_entities call is not using list comprehensions."""
        root_name = node.root().name

        # we only need to check components
        if not root_name.startswith("homeassistant.components"):
            return

        func_name = node.func.as_string()
        if func_name == "async_add_entities":
            # we only want to check calls where
            # update_before_add is not set
            if len(node.args) > 1:
                return

            if isinstance(node.args[0], nodes.ListComp):
                self.add_message("hass-enforce-non-list-comprehensions", node=node)
                return


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassEnforceNonListComprehensionsChecker(linter))
