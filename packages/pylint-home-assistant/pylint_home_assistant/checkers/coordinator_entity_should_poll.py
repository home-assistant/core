"""Checker for ``_attr_should_poll`` on coordinator entities.

``CoordinatorEntity`` overrides ``should_poll`` to always return ``False``, as
the coordinator tells its entities when it has new data. ``_attr_should_poll``
is only read by ``Entity.should_poll``, so setting it on a coordinator entity
has no effect.

``W7455`` (``home-assistant-coordinator-entity-should-poll``)
"""

import astroid
from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import is_integration_module

_ATTR_SHOULD_POLL = "_attr_should_poll"
_BASE_COORDINATOR_ENTITY_QNAME = (
    "homeassistant.helpers.update_coordinator.BaseCoordinatorEntity"
)


class _UnresolvedMroError(Exception):
    """Raised when the MRO of a class can't be worked out."""


def _base_classes(node: nodes.ClassDef) -> list[nodes.ClassDef]:
    """Return the base classes of *node*, including subscripted generic bases."""
    bases: list[nodes.ClassDef] = []
    for base in node.bases:
        expression = base.value if isinstance(base, nodes.Subscript) else base
        try:
            inferred = next(
                (
                    item
                    for item in expression.infer()
                    if isinstance(item, nodes.ClassDef)
                ),
                None,
            )
        except astroid.exceptions.InferenceError:
            inferred = None
        if inferred is None or inferred.qname() == node.qname():
            raise _UnresolvedMroError
        bases.append(inferred)
    return bases


def _mro(node: nodes.ClassDef) -> list[nodes.ClassDef]:
    """Return the C3 linearization of *node*.

    astroid's own ``mro()`` drops subscripted bases such as
    ``CoordinatorEntity[MyCoordinator]``, so it is computed here.
    """
    bases = _base_classes(node)
    sequences = [_mro(base) for base in bases] + [bases]
    result = [node]
    while sequences := [sequence for sequence in sequences if sequence]:
        for sequence in sequences:
            head = sequence[0].qname()
            if not any(
                head in (item.qname() for item in other[1:]) for other in sequences
            ):
                break
        else:
            raise _UnresolvedMroError
        result.append(sequence[0])
        sequences = [
            sequence[1:] if sequence[0].qname() == head else sequence
            for sequence in sequences
        ]
    return result


def _should_poll_from_coordinator_entity(node: nodes.ClassDef) -> bool:
    """Return True if ``should_poll`` resolves to ``BaseCoordinatorEntity``'s."""
    try:
        mro = _mro(node)
    except _UnresolvedMroError:
        return False
    for klass in mro:
        if "should_poll" in klass.locals:
            qname: str = klass.qname()
            return qname == _BASE_COORDINATOR_ENTITY_QNAME
    return False


def _should_poll_assignments(node: nodes.ClassDef) -> list[nodes.NodeNG]:
    """Return the statements of the class that set ``_attr_should_poll``."""
    assignments: list[nodes.NodeNG] = []
    for item in node.body:
        match item:
            case nodes.Assign(targets=targets) if any(
                isinstance(target, nodes.AssignName)
                and target.name == _ATTR_SHOULD_POLL
                for target in targets
            ):
                assignments.append(item)
            case nodes.AnnAssign(target=nodes.AssignName(name=name), value=value) if (
                name == _ATTR_SHOULD_POLL and value is not None
            ):
                assignments.append(item)
            case nodes.FunctionDef():
                assignments.extend(
                    assign.parent
                    for assign in item.nodes_of_class(
                        nodes.AssignAttr, skip_klass=nodes.ClassDef
                    )
                    if assign.attrname == _ATTR_SHOULD_POLL
                    and isinstance(assign.expr, nodes.Name)
                    and assign.expr.name == "self"
                )
    return assignments


class CoordinatorEntityShouldPollChecker(BaseChecker):
    """Checker for ``_attr_should_poll`` on coordinator entities."""

    name = "home_assistant_coordinator_entity_should_poll"
    priority = -1
    msgs = {
        "W7455": (
            (
                "`_attr_should_poll` has no effect on a coordinator entity, "
                "`CoordinatorEntity.should_poll` always returns `False`"
            ),
            "home-assistant-coordinator-entity-should-poll",
            (
                "Used when a `CoordinatorEntity` sets `_attr_should_poll`. "
                "`CoordinatorEntity` overrides `should_poll`, so the attribute "
                "is never read."
            ),
        ),
    }
    options = ()

    def visit_classdef(self, node: nodes.ClassDef) -> None:
        """Check classes that set ``_attr_should_poll``."""
        if not is_integration_module(node.root().name):
            return
        if not (assignments := _should_poll_assignments(node)):
            return
        if not _should_poll_from_coordinator_entity(node):
            return
        for assignment in assignments:
            self.add_message(
                "home-assistant-coordinator-entity-should-poll", node=assignment
            )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(CoordinatorEntityShouldPollChecker(linter))
