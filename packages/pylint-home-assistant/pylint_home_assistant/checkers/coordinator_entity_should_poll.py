"""Checker for ``_attr_should_poll`` on coordinator entities.

``CoordinatorEntity`` overrides ``should_poll`` to always return ``False``, as
the coordinator tells its entities when it has new data. ``_attr_should_poll``
is only read by ``Entity.should_poll``, so setting it on a coordinator entity
has no effect.

``W7455`` (``home-assistant-coordinator-entity-should-poll``)
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.ast_utils import extended_ancestors
from pylint_home_assistant.helpers.module_info import is_integration_module

_ATTR_SHOULD_POLL = "_attr_should_poll"
_BASE_COORDINATOR_ENTITY_QNAME = (
    "homeassistant.helpers.update_coordinator.BaseCoordinatorEntity"
)
_ENTITY_QNAME = "homeassistant.helpers.entity.Entity"


def _should_poll_from_coordinator_entity(node: nodes.ClassDef) -> bool:
    """Return True if ``should_poll`` comes from ``BaseCoordinatorEntity``.

    ``BaseCoordinatorEntity`` subclasses ``Entity``, so it comes first in the
    MRO. Any other class that defines ``should_poll`` might come before it, in
    which case ``_attr_should_poll`` may still be read.
    """
    if "should_poll" in node.locals:
        return False
    is_coordinator_entity = False
    for ancestor in extended_ancestors(node):
        qname = ancestor.qname()
        if qname == _BASE_COORDINATOR_ENTITY_QNAME:
            is_coordinator_entity = True
        elif qname != _ENTITY_QNAME and "should_poll" in ancestor.locals:
            return False
    return is_coordinator_entity


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
