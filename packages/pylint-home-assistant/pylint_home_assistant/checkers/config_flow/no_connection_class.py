"""Checker for the removed CONNECTION_CLASS attribute in config flows."""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.const import Module
from pylint_home_assistant.helpers.module_info import parse_module

_CONNECTION_CLASS = "CONNECTION_CLASS"


class HassEnforceConfigFlowNoConnectionClassChecker(BaseChecker):
    """Checker for CONNECTION_CLASS in config flows."""

    name = "home_assistant_enforce_config_flow_no_connection_class"
    priority = -1
    msgs = {
        "W7438": (
            "Config flow should not set CONNECTION_CLASS",
            "home-assistant-config-flow-connection-class",
            "Used when a config flow class sets CONNECTION_CLASS. The attribute "
            "is no longer used by Home Assistant and should not be set.",
        ),
    }
    options = ()

    def visit_assign(self, node: nodes.Assign) -> None:
        """Check class-level assignments."""
        if any(
            isinstance(target, nodes.AssignName) and target.name == _CONNECTION_CLASS
            for target in node.targets
        ):
            self._check(node)

    def visit_annassign(self, node: nodes.AnnAssign) -> None:
        """Check annotated class-level assignments."""
        if (
            isinstance(node.target, nodes.AssignName)
            and node.target.name == _CONNECTION_CLASS
        ):
            self._check(node)

    def _check(self, node: nodes.Assign | nodes.AnnAssign) -> None:
        """Add a message if the assignment is in a config flow class body."""
        parsed = parse_module(node.root().name)
        if parsed is None or parsed.module != Module.CONFIG_FLOW:
            return
        if not isinstance(node.parent, nodes.ClassDef):
            return
        self.add_message("home-assistant-config-flow-connection-class", node=node)


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassEnforceConfigFlowNoConnectionClassChecker(linter))
