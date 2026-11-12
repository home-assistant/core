"""Checker for entities that set their own ``entity_id``.

Home Assistant generates the ``entity_id`` of an entity from its name when the
entity is added, and users can change it in the entity registry. An entity
that sets ``entity_id`` itself bypasses this, so it should not do so.

Flagged in integration modules, on ``Entity`` subclasses:

- a class-body ``entity_id = ...`` assignment, and
- a ``self.entity_id = ...`` assignment in a method of the class.

Internal integrations (``quality_scale: internal`` in the manifest) are not
checked.

``W7461`` (``home-assistant-entity-sets-entity-id``)
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.entity_class import inherits_from_entity
from pylint_home_assistant.helpers.integration import is_internal_integration
from pylint_home_assistant.helpers.module_info import is_integration_module

_ENTITY_ID = "entity_id"


def _enclosing_class(node: nodes.NodeNG) -> nodes.ClassDef | None:
    """Return the closest class that encloses *node*."""
    parent = node.parent
    while parent is not None and not isinstance(parent, nodes.ClassDef):
        parent = parent.parent
    return parent


class HassEntitySetsEntityIdChecker(BaseChecker):
    """Flag entities that set their own ``entity_id``."""

    name = "home_assistant_entity_sets_entity_id"
    priority = -1
    msgs = {
        "W7461": (
            (
                "Entity class `%s` sets its own `entity_id`; let Home "
                "Assistant generate it from the entity name instead"
            ),
            "home-assistant-entity-sets-entity-id",
            (
                "Used when an Entity subclass assigns `entity_id` in its "
                "class body or assigns `self.entity_id`. Home Assistant "
                "generates the entity ID from the entity name, and users can "
                "change it in the entity registry."
            ),
        ),
    }
    options = ()

    _check_module: bool

    def visit_module(self, node: nodes.Module) -> None:
        """Cache per-module state."""
        self._check_module = is_integration_module(
            node.name
        ) and not is_internal_integration(node)

    def visit_assignname(self, node: nodes.AssignName) -> None:
        """Flag class-body ``entity_id = ...`` assignments."""
        if not self._check_module or node.name != _ENTITY_ID:
            return
        class_node = node.frame()
        if not isinstance(class_node, nodes.ClassDef):
            return
        if isinstance(node.parent, nodes.AnnAssign) and node.parent.value is None:
            return
        self._check(node, class_node)

    def visit_assignattr(self, node: nodes.AssignAttr) -> None:
        """Flag ``self.entity_id = ...`` assignments."""
        if not self._check_module or node.attrname != _ENTITY_ID:
            return
        if not isinstance(node.expr, nodes.Name) or node.expr.name != "self":
            return
        if (class_node := _enclosing_class(node)) is None:
            return
        self._check(node, class_node)

    def _check(self, node: nodes.NodeNG, class_node: nodes.ClassDef) -> None:
        """Add the message if *class_node* is an entity."""
        if not inherits_from_entity(class_node):
            return
        self.add_message(
            "home-assistant-entity-sets-entity-id",
            node=node,
            args=(class_node.name,),
        )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassEntitySetsEntityIdChecker(linter))
