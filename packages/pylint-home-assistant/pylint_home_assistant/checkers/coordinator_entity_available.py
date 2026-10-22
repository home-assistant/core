"""Checker for ``available`` overrides on coordinator entities.

``CoordinatorEntity.available`` returns ``coordinator.last_update_success``,
so the entity becomes unavailable when an update fails. An override that
takes its availability only from ``coordinator.data`` keeps the entity
available with stale data after a failed update, because the coordinator keeps
the data of the last successful update.

Overrides that use ``super().available`` or ``last_update_success``, or that
have a source of their own (a client, a device, a websocket or
``_attr_available``), are not flagged, and neither are entities of a push
coordinator (no ``update_interval``). Properties and methods of the entity and
the coordinator are followed, so ``self.data`` reading ``coordinator.data``
counts as coordinator data.

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


_DATA = "data"
_OTHER = "other"
_COORDINATOR_AVAILABILITY = "coordinator availability"
_MAX_DEPTH = 3


def _chain_top(node: nodes.NodeNG) -> nodes.NodeNG:
    """Return the outermost attribute, subscript or call built on *node*."""
    while True:
        match node.parent:
            case (
                nodes.Attribute(expr=base)
                | nodes.Subscript(value=base)
                | nodes.Call(func=base)
            ) if base is node:
                node = node.parent
            case _:
                return node


def _decides_result(node: nodes.NodeNG) -> bool:
    """Return True if the value of *node* is used as a truth value."""
    match node.parent:
        case nodes.BoolOp() | nodes.Return() | nodes.UnaryOp():
            return True
        case nodes.If(test=test) | nodes.IfExp(test=test):
            return test is node
    return False


def _member(class_node: nodes.ClassDef | None, name: str) -> nodes.FunctionDef | None:
    """Return the property or method *name* that the integration defines."""
    if class_node is None:
        return None
    integration = ".".join(class_node.root().name.split(".")[:3]) + "."
    for klass in (class_node, *extended_ancestors(class_node)):
        if not klass.qname().startswith(integration):
            continue
        for node in klass.locals.get(name, []):
            if isinstance(node, nodes.FunctionDef):
                return node
    return None


class _Sources:
    """Collect where an ``available`` override gets its value from."""

    def __init__(
        self, entity: nodes.ClassDef, coordinator: nodes.ClassDef | None
    ) -> None:
        """Initialize with the entity and its coordinator class."""
        self._classes = {"entity": entity, "coordinator": coordinator}
        self._seen: set[nodes.FunctionDef] = set()
        self.found: set[str] = set()

    def visit(self, function: nodes.FunctionDef, owner: str, depth: int = 0) -> None:
        """Collect the sources of *function*, a member of *owner*."""
        if function in self._seen or depth > _MAX_DEPTH:
            return
        self._seen.add(function)
        for attribute in function.nodes_of_class(
            nodes.Attribute, skip_klass=nodes.FunctionDef
        ):
            match attribute:
                case (
                    nodes.Attribute(attrname="last_update_success")
                    | nodes.Attribute(
                        attrname="available",
                        expr=nodes.Call(func=nodes.Name(name="super"))
                        | nodes.Name(name="CoordinatorEntity"),
                    )
                ):
                    self.found.add(_COORDINATOR_AVAILABILITY)
                case nodes.Attribute(expr=nodes.Name(name="self"), attrname=name):
                    self._visit_self_attribute(attribute, name, owner, depth)

    def _visit_self_attribute(
        self, attribute: nodes.Attribute, name: str, owner: str, depth: int
    ) -> None:
        """Classify ``self.<name>`` inside a member of *owner*."""
        if owner == "entity" and name == "coordinator":
            match attribute.parent:
                case nodes.Attribute(attrname="data", expr=base) if base is attribute:
                    self.found.add(_DATA)
                case nodes.Attribute(attrname=member_name, expr=base) if (
                    base is attribute
                ):
                    self._visit_member(member_name, "coordinator", depth)
                case _:
                    # The coordinator itself is passed on
                    self.found.add(_OTHER)
            return
        if owner == "coordinator" and name == "data":
            self.found.add(_DATA)
            return
        if name == "_attr_available":
            self.found.add(_OTHER)
            return
        if name == "hass":
            return
        if owner == "coordinator" or _member(self._classes[owner], name):
            self._visit_member(name, owner, depth)
            return
        top = _chain_top(attribute)
        # Description callables only see what they are given
        if isinstance(top, nodes.Call) and name == "entity_description":
            return
        if _decides_result(top):
            self.found.add(_OTHER)

    def _visit_member(self, name: str, owner: str, depth: int) -> None:
        """Follow a property or method, or count an unknown member as other."""
        if (member := _member(self._classes[owner], name)) is None:
            self.found.add(_OTHER)
            return
        self.visit(member, owner, depth + 1)


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
        ):
            return

        coordinator = _coordinator_class(node)
        sources = _Sources(node, coordinator)
        sources.visit(available, "entity")
        if (
            _DATA not in sources.found
            or _OTHER in sources.found
            or _COORDINATOR_AVAILABILITY in sources.found
        ):
            return

        if coordinator is not None and _is_push_coordinator(coordinator):
            return

        self.add_message("home-assistant-coordinator-entity-available", node=available)


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(CoordinatorEntityAvailableChecker(linter))
