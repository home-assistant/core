"""Checker for ``available`` overrides on coordinator entities.

``CoordinatorEntity.available`` returns ``coordinator.last_update_success``,
so the entity becomes unavailable when an update fails. An override that
doesn't use ``super().available`` (or ``last_update_success``) keeps the
entity available with stale data after a failed update. An override that
only returns ``True`` is deliberate and not flagged.

``W7449`` (``home-assistant-coordinator-entity-available``)
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.ast_utils import extended_ancestors
from pylint_home_assistant.helpers.module_info import is_integration_module

_COORDINATOR_ENTITY_QNAME = "homeassistant.helpers.update_coordinator.CoordinatorEntity"


def _is_coordinator_entity(class_node: nodes.ClassDef) -> bool:
    """Return True if the class is a ``CoordinatorEntity``."""
    return any(
        ancestor.qname() == _COORDINATOR_ENTITY_QNAME
        for ancestor in extended_ancestors(class_node)
    )


def _uses_coordinator_availability(function: nodes.FunctionDef) -> bool:
    """Return True if the function uses the coordinator's availability."""
    for attribute in function.nodes_of_class(nodes.Attribute):
        match attribute:
            case nodes.Attribute(attrname="last_update_success"):
                return True
            case nodes.Attribute(
                attrname="available",
                expr=nodes.Call(func=nodes.Name(name="super"))
                | nodes.Name(name="CoordinatorEntity"),
            ):
                return True
    return False


def _always_available(function: nodes.FunctionDef) -> bool:
    """Return True if the function only returns ``True``."""
    returns = list(function.nodes_of_class(nodes.Return))
    return bool(returns) and all(
        isinstance(node.value, nodes.Const) and node.value.value is True
        for node in returns
    )


class CoordinatorEntityAvailableChecker(BaseChecker):
    """Checker for ``available`` overrides on coordinator entities."""

    name = "home_assistant_coordinator_entity_available"
    priority = -1
    msgs = {
        "W7449": (
            (
                "`available` overrides `CoordinatorEntity.available` without "
                "using `super().available`"
            ),
            "home-assistant-coordinator-entity-available",
            (
                "Used when a CoordinatorEntity overrides `available` without "
                "using `super().available` or `coordinator.last_update_success`, "
                "so the entity stays available when a coordinator update fails."
            ),
        ),
    }
    options = ()

    _in_integration = False

    def visit_module(self, node: nodes.Module) -> None:
        """Only check integration modules."""
        self._in_integration = is_integration_module(node.name)

    def visit_classdef(self, node: nodes.ClassDef) -> None:
        """Check the ``available`` override of coordinator entities."""
        if not self._in_integration:
            return

        available = node.locals.get("available", [None])[0]
        if (
            not isinstance(available, nodes.FunctionDef)
            or available.parent is not node
            or not _is_coordinator_entity(node)
            or _uses_coordinator_availability(available)
            # Deliberately available, also when the coordinator fails
            or _always_available(available)
        ):
            return

        self.add_message("home-assistant-coordinator-entity-available", node=available)


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(CoordinatorEntityAvailableChecker(linter))
