"""Checker for how a ``DataUpdateCoordinator`` handles its config entry.

Most integrations define a typed config entry, such as
``type MyConfigEntry = ConfigEntry[MyCoordinator]``. A coordinator should use
that type for its config entry, so ``self.config_entry.runtime_data`` is typed
too. A plain ``ConfigEntry`` loses that.

``DataUpdateCoordinator.__init__`` already stores the ``config_entry`` it is
given, so assigning ``self.config_entry`` again in the subclass is redundant.

``W7447`` (``home-assistant-coordinator-untyped-config-entry``)
``W7448`` (``home-assistant-coordinator-redundant-config-entry``)
"""

from functools import cache
from pathlib import Path

import astroid
from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.ast_utils import extended_ancestors
from pylint_home_assistant.helpers.integration import get_integration_dir
from pylint_home_assistant.helpers.module_info import is_integration_module

_COORDINATOR_QNAME = "homeassistant.helpers.update_coordinator.DataUpdateCoordinator"


def _is_plain_config_entry(node: nodes.NodeNG | None) -> bool:
    """Return True for ``ConfigEntry`` without type arguments."""
    match node:
        case nodes.Name(name="ConfigEntry") | nodes.Attribute(attrname="ConfigEntry"):
            return True
        # ConfigEntry | None
        case nodes.BinOp(op="|", left=left, right=right):
            return _is_plain_config_entry(left) or _is_plain_config_entry(right)
    return False


def _is_typed_config_entry(node: nodes.NodeNG) -> bool:
    """Return True for ``ConfigEntry[...]``."""
    match node:
        case nodes.Subscript(
            value=nodes.Name(name="ConfigEntry")
            | nodes.Attribute(attrname="ConfigEntry")
        ):
            return True
    return False


@cache
def _typed_config_entries(integration_dir: Path) -> tuple[str, ...]:
    """Return the names of the typed config entries an integration defines."""
    names: set[str] = set()
    for source in integration_dir.rglob("*.py"):
        try:
            module = astroid.parse(source.read_text())
        except astroid.exceptions.AstroidSyntaxError, OSError:
            continue
        for node in module.body:
            match node:
                # type MyConfigEntry = ConfigEntry[MyCoordinator]
                case nodes.TypeAlias(name=nodes.AssignName(name=name), value=value) if (
                    _is_typed_config_entry(value)
                ):
                    names.add(name)
                # MyConfigEntry = ConfigEntry[MyCoordinator]
                case nodes.Assign(
                    targets=[nodes.AssignName(name=name)], value=value
                ) if _is_typed_config_entry(value):
                    names.add(name)
    return tuple(sorted(names))


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
        "W7447": (
            "Use the integration's typed config entry (%s) instead of `ConfigEntry`",
            "home-assistant-coordinator-untyped-config-entry",
            (
                "Used when a DataUpdateCoordinator types its config entry as a "
                "plain `ConfigEntry` while the integration defines a typed "
                "config entry, such as `type MyConfigEntry = "
                "ConfigEntry[MyCoordinator]`."
            ),
        ),
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

        if typed_entries := _typed_config_entries(self._integration_dir):
            self._check_untyped(node, typed_entries)

        if isinstance(
            init := node.locals.get("__init__", [None])[0], nodes.FunctionDef
        ):
            self._check_redundant(init)

    def _check_untyped(
        self, node: nodes.ClassDef, typed_entries: tuple[str, ...]
    ) -> None:
        """Flag ``config_entry`` annotated as a plain ``ConfigEntry``."""
        annotations: list[nodes.NodeNG] = [
            item.annotation
            for item in node.body
            if isinstance(item, nodes.AnnAssign)
            and isinstance(item.target, nodes.AssignName)
            and item.target.name == "config_entry"
        ]

        init = node.locals.get("__init__", [None])[0]
        if isinstance(init, nodes.FunctionDef):
            # The argument may have another name, such as ``entry``, when it is
            # passed on as ``config_entry=entry``
            names = {"config_entry"}
            match _config_entry_passed_to_super(init):
                case nodes.Name(name=name):
                    names.add(name)

            arguments = init.args
            for index, argument in enumerate([*arguments.args, *arguments.kwonlyargs]):
                if argument.name not in names:
                    continue
                annotation = (
                    arguments.annotations[index]
                    if index < len(arguments.args)
                    else arguments.kwonlyargs_annotations[index - len(arguments.args)]
                )
                annotations.append(annotation)

        for annotation in annotations:
            if _is_plain_config_entry(annotation):
                self.add_message(
                    "home-assistant-coordinator-untyped-config-entry",
                    node=annotation,
                    args=(", ".join(f"`{name}`" for name in typed_entries),),
                )

    def _check_redundant(self, init: nodes.FunctionDef) -> None:
        """Flag ``self.config_entry = ...`` when ``super()`` already stores it."""
        if _config_entry_passed_to_super(init) is None:
            return

        for assign in init.nodes_of_class(nodes.AssignAttr):
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
