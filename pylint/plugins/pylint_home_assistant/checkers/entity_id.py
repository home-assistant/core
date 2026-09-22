"""Checker that prohibits setting ``self.entity_id`` in integrations.

Home Assistant assigns an entity's ``entity_id`` automatically, derived
from the entity's platform together with its name (``has_entity_name``)
or the object id suggested via ``_attr_suggested_object_id`` /
``suggested_object_id``. Integrations should not set ``self.entity_id``
themselves: doing so bypasses the entity registry's collision handling
and the user's ability to rename an entity, and it hard-codes an
``entity_id`` that ignores the configured naming.

The check fires on ``self.entity_id = ...`` assignments (including
augmented and annotated assignments) at any depth inside a class that
inherits from ``homeassistant.helpers.entity.Entity``, in any
integration module.
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.entity_class import inherits_from_entity
from pylint_home_assistant.helpers.module_info import is_integration_module

_ATTR_NAME = "entity_id"


def _is_self_entity_id_target(target: nodes.NodeNG) -> bool:
    """Return True if the target is ``self.entity_id``."""
    match target:
        case nodes.AssignAttr(attrname=name, expr=nodes.Name(name="self")) if (
            name == _ATTR_NAME
        ):
            return True
    return False


class HassEnforceEntityIdChecker(BaseChecker):
    """Checker that flags ``self.entity_id`` assignments in entity classes."""

    name = "home_assistant_entity_id"
    priority = -1
    msgs = {
        "W7438": (
            (
                "Do not set `self.entity_id`; Home Assistant generates the "
                "entity_id from the entity's platform and name. Provide a "
                "unique ID and name instead, or `_attr_suggested_object_id`"
            ),
            "home-assistant-entity-id",
            (
                "Used when an entity class assigns to `self.entity_id`. Home "
                "Assistant derives the entity_id automatically from the "
                "entity's platform and name and lets users rename entities "
                "via the entity registry. Setting entity_id directly bypasses "
                "that mechanism."
            ),
        ),
    }
    options = ()

    _is_integration_module: bool

    def visit_module(self, node: nodes.Module) -> None:
        """Cache per-module state."""
        self._is_integration_module = is_integration_module(node.name)

    def visit_classdef(self, node: nodes.ClassDef) -> None:
        """Flag ``self.entity_id`` assignments inside entity classes."""
        if not self._is_integration_module:
            return
        if not inherits_from_entity(node):
            return
        for method in node.body:
            if not isinstance(method, nodes.FunctionDef | nodes.AsyncFunctionDef):
                continue
            for assign in method.nodes_of_class(
                (nodes.Assign, nodes.AnnAssign, nodes.AugAssign)
            ):
                match assign:
                    case nodes.Assign(targets=targets):
                        target_list = list(targets)
                    case (
                        nodes.AnnAssign(target=target) | nodes.AugAssign(target=target)
                    ):
                        target_list = [target]
                    case _:  # pragma: no cover
                        continue
                for target in target_list:
                    if _is_self_entity_id_target(target):
                        self.add_message(
                            "home-assistant-entity-id",
                            node=target,
                        )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassEnforceEntityIdChecker(linter))
