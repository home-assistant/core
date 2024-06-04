"""Plugin to enforce type hints on specific functions."""

from __future__ import annotations

import re

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

_MODULE_REGEX: re.Pattern[str] = re.compile(r"^homeassistant\.components\.\w+(\.\w+)?$")


def _get_module_platform(module_name: str) -> str | None:
    """Return the platform for the module name."""
    if not (module_match := _MODULE_REGEX.match(module_name)):
        # Ensure `homeassistant.components.<component>`
        # Or `homeassistant.components.<component>.<platform>`
        return None

    platform = module_match.groups()[0]
    return platform.lstrip(".") if platform else "__init__"


class HassInheritanceChecker(BaseChecker):
    """Checker for invalid inheritance."""

    name = "hass_inheritance"
    priority = -1
    msgs = {
        "W7411": (
            "Invalid inheritance: %s",
            "hass-invalid-inheritance",
            "Used when a class has inheritance has issues",
        ),
    }
    options = ()

    _module_name: str
    _module_platform: str | None

    def visit_module(self, node: nodes.Module) -> None:
        """Populate matchers for a Module node."""
        self._module_name = node.name
        self._module_platform = _get_module_platform(node.name)

    def visit_classdef(self, node: nodes.ClassDef) -> None:
        """Apply relevant type hint checks on a ClassDef node."""
        if self._module_platform not in {"number", "sensor"}:
            return

        ancestors = [a.name for a in node.ancestors()]
        if (
            "RestoreEntity" in ancestors
            and "SensorEntity" in ancestors
            and "RestoreSensor" not in ancestors
        ):
            self.add_message(
                "hass-invalid-inheritance",
                node=node,
                args="SensorEntity and RestoreEntity should not be combined, please use RestoreSensor",
            )
        elif (
            "RestoreEntity" in ancestors
            and "NumberEntity" in ancestors
            and "RestoreNumber" not in ancestors
        ):
            self.add_message(
                "hass-invalid-inheritance",
                node=node,
                args="NumberEntity and RestoreEntity should not be combined, please use RestoreNumber",
            )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassInheritanceChecker(linter))
