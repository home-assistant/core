"""Checker for how a ``DataUpdateCoordinator`` handles its config entry.

``DataUpdateCoordinator.__init__`` already stores the ``config_entry`` it is
given, so assigning ``self.config_entry`` again in the subclass is redundant.

``W7448`` (``home-assistant-coordinator-redundant-config-entry``)
"""

from pathlib import Path

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.ast_utils import extended_ancestors
from pylint_home_assistant.helpers.integration import get_integration_dir
from pylint_home_assistant.helpers.module_info import is_integration_module

_COORDINATOR_QNAME = "homeassistant.helpers.update_coordinator.DataUpdateCoordinator"


def _is_coordinator(class_node: nodes.ClassDef) -> bool:
    """Return True if the class is a ``DataUpdateCoordinator``."""
    return any(
        ancestor.qname() == _COORDINATOR_QNAME
        for ancestor in extended_ancestors(class_node)
    )


def _config_entry_passed_to_super(init: nodes.FunctionDef) -> nodes.NodeNG | None:
    """Return what ``__init__`` passes as ``config_entry`` to ``super().__init__``."""
    for call in init.nodes_of_class(nodes.Call):
        match call.func:
            case nodes.Attribute(
                attrname="__init__",
                expr=nodes.Call(func=nodes.Name(name="super")),
            ):
                for keyword in call.keywords:
                    if keyword.arg == "config_entry":
                        return keyword.value
    return None


class CoordinatorConfigEntryChecker(BaseChecker):
    """Checker for how a coordinator handles its config entry."""

    name = "home_assistant_coordinator_config_entry"
    priority = -1
    msgs = {
        "W7448": (
            (
                "`self.config_entry` is already set by "
                "`DataUpdateCoordinator.__init__`, remove this assignment"
            ),
            "home-assistant-coordinator-redundant-config-entry",
            (
                "Used when a DataUpdateCoordinator assigns `self.config_entry` "
                "while it also passes `config_entry` to `super().__init__`, "
                "which already stores it."
            ),
        ),
    }
    options = ()

    _integration_dir: Path | None = None

    def visit_module(self, node: nodes.Module) -> None:
        """Record the integration directory for integration modules."""
        self._integration_dir = (
            get_integration_dir(node) if is_integration_module(node.name) else None
        )

    def visit_classdef(self, node: nodes.ClassDef) -> None:
        """Check coordinator classes."""
        if self._integration_dir is None or not _is_coordinator(node):
            return

        if isinstance(
            init := node.locals.get("__init__", [None])[0], nodes.FunctionDef
        ):
            self._check_redundant(init)

    def _check_redundant(self, init: nodes.FunctionDef) -> None:
        """Flag ``self.config_entry = ...`` when ``super()`` already stores it."""
        if _config_entry_passed_to_super(init) is None:
            return

        for assign in init.nodes_of_class(nodes.AssignAttr):
            # self.config_entry: MyConfigEntry only narrows the type
            if (
                isinstance(assign.parent, nodes.AnnAssign)
                and assign.parent.value is None
            ):
                continue

            match assign:
                case nodes.AssignAttr(
                    attrname="config_entry", expr=nodes.Name(name="self")
                ):
                    self.add_message(
                        "home-assistant-coordinator-redundant-config-entry",
                        node=assign.parent,
                    )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(CoordinatorConfigEntryChecker(linter))
