"""Checker for invalid entity class inheritance."""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.const import Platform
from pylint_home_assistant.helpers.module_info import get_module_platform


class HassInheritanceChecker(BaseChecker):
    """Checker for invalid inheritance."""

    name = "home_assistant_inheritance"
    priority = -1
    msgs = {
        "E7401": (
            "Invalid inheritance: %s",
            "home-assistant-invalid-inheritance",
            "Used when a class has inheritance has issues",
        ),
    }
    options = ()

    _module_name: str
    _module_platform: str | None

    def visit_module(self, node: nodes.Module) -> None:
        """Populate matchers for a Module node."""
        self._module_name = node.name
        self._module_platform = get_module_platform(node.name)

    def visit_classdef(self, node: nodes.ClassDef) -> None:
        """Apply relevant type hint checks on a ClassDef node."""
        if self._module_platform not in {Platform.NUMBER, Platform.SENSOR}:
            return

        ancestors = [a.name for a in node.ancestors()]
        if (
            "RestoreEntity" in ancestors
            and "SensorEntity" in ancestors
            and "RestoreSensor" not in ancestors
        ):
            self.add_message(
                "home-assistant-invalid-inheritance",
                node=node,
                args="SensorEntity and RestoreEntity should not be combined, please use RestoreSensor",
            )
        elif (
            "RestoreEntity" in ancestors
            and "NumberEntity" in ancestors
            and "RestoreNumber" not in ancestors
        ):
            self.add_message(
                "home-assistant-invalid-inheritance",
                node=node,
                args="NumberEntity and RestoreEntity should not be combined, please use RestoreNumber",
            )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassInheritanceChecker(linter))
