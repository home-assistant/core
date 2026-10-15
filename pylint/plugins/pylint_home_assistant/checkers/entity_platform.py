"""Checker for entity platform integrations."""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.const import ENTITY_COMPONENTS
from pylint_home_assistant.helpers.module_info import parse_module


class HassEntityPlatformChecker(BaseChecker):
    """Checker for entity platform integrations."""

    name = "home_assistant_entity_platform"
    priority = -1
    msgs = {
        "C7417": (
            "Entity platform `%s` must define `__all__` in its package root",
            "home-assistant-entity-platform-missing-all",
            "Used when the package root of an entity platform integration "
            "does not define __all__",
        ),
    }
    options = ()

    def visit_module(self, node: nodes.Module) -> None:
        """Check the package root of entity platform integrations."""
        if (
            not node.package
            or (parsed_module := parse_module(node.name)) is None
            or parsed_module.module is not None
            or parsed_module.domain not in ENTITY_COMPONENTS
        ):
            return
        if "__all__" not in node.locals:
            self.add_message(
                "home-assistant-entity-platform-missing-all",
                node=node,
                args=(parsed_module.domain,),
            )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassEntityPlatformChecker(linter))
