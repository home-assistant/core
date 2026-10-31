"""Checker for coordinator classes that are subclassed without a type parameter.

``DataUpdateCoordinator`` and ``CoordinatorEntity`` are generic. Without a type
parameter, ``coordinator.data`` and ``self.coordinator`` lose their types, so
the type checker can't check the code that uses them.

``W7454`` (``home-assistant-coordinator-missing-type-parameter``)
"""

import astroid
from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import is_integration_module

_DATA_TYPE = "the type of the coordinator data"
_GENERIC_CLASSES: dict[str, str] = {
    "homeassistant.helpers.update_coordinator.CoordinatorEntity": "the coordinator",
    "homeassistant.helpers.update_coordinator.DataUpdateCoordinator": _DATA_TYPE,
    "homeassistant.helpers.update_coordinator.TimestampDataUpdateCoordinator": (
        _DATA_TYPE
    ),
}


class CoordinatorTypeParameterChecker(BaseChecker):
    """Checker for coordinator base classes without a type parameter."""

    name = "home_assistant_coordinator_type_parameter"
    priority = -1
    msgs = {
        "W7454": (
            "Add %s as type parameter: `%s[...]`",
            "home-assistant-coordinator-missing-type-parameter",
            (
                "Used when a class subclasses `DataUpdateCoordinator` or "
                "`CoordinatorEntity` without a type parameter, which leaves "
                "`coordinator.data` or `self.coordinator` untyped."
            ),
        ),
    }
    options = ()

    def visit_classdef(self, node: nodes.ClassDef) -> None:
        """Check the base classes of integration classes."""
        if not is_integration_module(node.root().name):
            return

        for base in node.bases:
            # A subscript base such as ``CoordinatorEntity[MyCoordinator]``
            # already has its type parameter
            if not isinstance(base, (nodes.Name, nodes.Attribute)):
                continue
            try:
                inferred = base.inferred()
            except astroid.exceptions.InferenceError:
                continue
            for base_class in inferred:
                if isinstance(base_class, nodes.ClassDef) and (
                    type_parameter := _GENERIC_CLASSES.get(base_class.qname())
                ):
                    self.add_message(
                        "home-assistant-coordinator-missing-type-parameter",
                        node=base,
                        args=(type_parameter, base_class.name),
                    )
                    break


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(CoordinatorTypeParameterChecker(linter))
