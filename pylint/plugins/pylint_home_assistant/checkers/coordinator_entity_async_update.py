"""Checker for ``async_update`` overrides on coordinator entities.

``CoordinatorEntity.async_update`` asks the coordinator for a refresh.
Coordinator entities don't poll, so it normally only runs for the
``homeassistant.update_entity`` action (and for ``update_before_add`` or
``async_schedule_update_ha_state(True)``). An override that doesn't call the parent fetches data
outside the coordinator, so the other entities don't get it and the
coordinator's error handling and debouncing are skipped.

Not flagged: overrides that call ``super().async_update()``, overrides that
do nothing (entities of a push coordinator, which can't refresh on request),
and entities of the integration that turn polling back on.

``W7451`` (``home-assistant-coordinator-entity-async-update``)
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.ast_utils import extended_ancestors
from pylint_home_assistant.helpers.module_info import is_integration_module

_COORDINATOR_ENTITY_QNAMES = {
    "homeassistant.helpers.update_coordinator.BaseCoordinatorEntity",
    "homeassistant.helpers.update_coordinator.CoordinatorEntity",
}


def _calls_parent_update(function: nodes.FunctionDef) -> bool:
    """Return True if the function calls the parent ``async_update``."""
    for call in function.nodes_of_class(nodes.Call):
        match call.func:
            case nodes.Attribute(
                attrname="async_update",
                expr=nodes.Call(func=nodes.Name(name="super"))
                | nodes.Name(name="BaseCoordinatorEntity" | "CoordinatorEntity"),
            ):
                return True
    return False


def _is_noop(function: nodes.FunctionDef) -> bool:
    """Return True if the function body is empty apart from its docstring."""
    return all(
        isinstance(node, nodes.Pass)
        or (isinstance(node, nodes.Expr) and isinstance(node.value, nodes.Const))
        for node in function.body
    )


def _returns_false(function: nodes.FunctionDef) -> bool:
    """Return True if the function only does ``return False``."""
    match function.body:
        case [nodes.Return(value=nodes.Const(value=False))]:
            return True
    return False


def _polls(class_node: nodes.ClassDef) -> bool:
    """Return True if a class of the integration turns polling back on."""
    integration = ".".join(class_node.root().name.split(".")[:3]) + "."
    for klass in (class_node, *extended_ancestors(class_node)):
        if not klass.qname().startswith(integration):
            continue
        for node in klass.locals.get("should_poll", []):
            if isinstance(node, nodes.FunctionDef) and not _returns_false(node):
                return True
        for node in klass.locals.get("_attr_should_poll", []):
            match node.parent:
                case (
                    nodes.Assign(value=nodes.Const(value=True))
                    | nodes.AnnAssign(value=nodes.Const(value=True))
                ):
                    return True
    return False


class CoordinatorEntityAsyncUpdateChecker(BaseChecker):
    """Checker for ``async_update`` overrides on coordinator entities."""

    name = "home_assistant_coordinator_entity_async_update"
    priority = -1
    msgs = {
        "W7451": (
            (
                "`async_update` overrides `CoordinatorEntity.async_update` "
                "without calling `super().async_update()`"
            ),
            "home-assistant-coordinator-entity-async-update",
            (
                "Used when a CoordinatorEntity overrides `async_update` without "
                "calling `super().async_update()`, so a requested update "
                "bypasses the coordinator. Fetch the data in the coordinator."
            ),
        ),
    }
    options = ()

    _in_integration = False

    def visit_module(self, node: nodes.Module) -> None:
        """Only check integration modules."""
        self._in_integration = is_integration_module(node.name)

    def visit_classdef(self, node: nodes.ClassDef) -> None:
        """Check the ``async_update`` override of coordinator entities."""
        if not self._in_integration:
            return

        async_update = node.locals.get("async_update", [None])[0]
        if (
            not isinstance(async_update, nodes.FunctionDef)
            or async_update.parent is not node
            or _calls_parent_update(async_update)
            or _is_noop(async_update)
            or not any(
                ancestor.qname() in _COORDINATOR_ENTITY_QNAMES
                for ancestor in extended_ancestors(node)
            )
            or _polls(node)
        ):
            return

        self.add_message(
            "home-assistant-coordinator-entity-async-update", node=async_update
        )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(CoordinatorEntityAsyncUpdateChecker(linter))
