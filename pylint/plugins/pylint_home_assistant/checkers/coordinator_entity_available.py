"""Checker for ``available`` overrides on coordinator entities.

``CoordinatorEntity.available`` returns ``coordinator.last_update_success``,
so the entity becomes unavailable when an update fails. An override that
doesn't use ``super().available`` (or ``last_update_success``) keeps the
entity available with stale data after a failed update. An override that
only returns ``True`` is deliberate and not flagged, and neither are entities
of a push coordinator (no ``update_interval``), which have their own
availability source.

``W7449`` (``home-assistant-coordinator-entity-available``)
"""

import astroid
from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.ast_utils import extended_ancestors
from pylint_home_assistant.helpers.module_info import is_integration_module

_COORDINATOR_QNAME = "homeassistant.helpers.update_coordinator.DataUpdateCoordinator"
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


def _returns_true(node: nodes.NodeNG) -> bool:
    """Return True for ``return True``."""
    return (
        isinstance(node, nodes.Return)
        and isinstance(node.value, nodes.Const)
        and node.value.value is True
    )


def _always_available(function: nodes.FunctionDef) -> bool:
    """Return True if the function only returns ``True``."""
    # Without a final return, the function can fall through and return None
    return _returns_true(function.body[-1]) and all(
        _returns_true(node)
        for node in function.nodes_of_class(
            nodes.Return, skip_klass=(nodes.FunctionDef, nodes.Lambda)
        )
    )


def _coordinator_class(class_node: nodes.ClassDef) -> nodes.ClassDef | None:
    """Return the coordinator class from a ``CoordinatorEntity[...]`` base."""
    for klass in (class_node, *extended_ancestors(class_node)):
        for base in klass.bases:
            if not isinstance(base, nodes.Subscript):
                continue
            match base.slice:
                # CoordinatorEntity["MyCoordinator"]
                case nodes.Const(value=str(name)):
                    inferred = klass.root().locals.get(name, [None])[0]
                case _:
                    try:
                        inferred = next(base.slice.infer())
                    except astroid.exceptions.InferenceError, StopIteration:
                        continue
            if isinstance(inferred, nodes.ClassDef) and any(
                ancestor.qname() == _COORDINATOR_QNAME
                for ancestor in extended_ancestors(inferred)
            ):
                return inferred
    return None


def _is_push_coordinator(coordinator: nodes.ClassDef) -> bool:
    """Return True if the coordinator never polls.

    A push coordinator gets its data through ``async_set_updated_data``, so
    ``last_update_success`` doesn't reflect whether the device is reachable.
    """
    passes_no_interval = False
    for klass in (coordinator, *coordinator.ancestors()):
        if klass.qname() == _COORDINATOR_QNAME:
            break
        for assign in klass.nodes_of_class(nodes.AssignAttr):
            if assign.attrname == "update_interval":
                return False
        init = klass.locals.get("__init__", [None])[0]
        if not isinstance(init, nodes.FunctionDef):
            continue
        for call in init.nodes_of_class(nodes.Call):
            match call.func:
                case nodes.Attribute(
                    attrname="__init__",
                    expr=nodes.Call(func=nodes.Name(name="super")),
                ):
                    for keyword in call.keywords:
                        # **kwargs may pass an interval
                        if keyword.arg is None or (
                            keyword.arg == "update_interval"
                            and not (
                                isinstance(keyword.value, nodes.Const)
                                and keyword.value.value is None
                            )
                        ):
                            return False
                    passes_no_interval = True
    return passes_no_interval


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

        if (
            coordinator := _coordinator_class(node)
        ) is not None and _is_push_coordinator(coordinator):
            return

        self.add_message("home-assistant-coordinator-entity-available", node=available)


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(CoordinatorEntityAvailableChecker(linter))
