"""Checker for setting ``runtime_data`` on an untyped ``ConfigEntry``.

``ConfigEntry`` is generic over its ``runtime_data``. When code sets
``entry.runtime_data`` while ``entry`` is annotated as a plain ``ConfigEntry``,
``runtime_data`` is typed as ``Any`` and the type checker can't help. The entry
should use a typed config entry, such as
``type MyConfigEntry = ConfigEntry[MyData]``, instead.

``W7460`` (``home-assistant-runtime-data-untyped-config-entry``)
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import is_integration_module


def _is_plain_config_entry(node: nodes.NodeNG | None) -> bool:
    """Return True for ``ConfigEntry`` without type arguments."""
    match node:
        case nodes.Name(name="ConfigEntry") | nodes.Attribute(attrname="ConfigEntry"):
            return True
        # ConfigEntry | None
        case nodes.BinOp(op="|", left=left, right=right):
            return _is_plain_config_entry(left) or _is_plain_config_entry(right)
    return False


def _argument_annotation(arguments: nodes.Arguments, name: str) -> nodes.NodeNG | None:
    """Return the annotation of argument *name*."""
    for argument, annotation in zip(
        [
            *(arguments.posonlyargs or []),
            *(arguments.args or []),
            *arguments.kwonlyargs,
        ],
        [
            *arguments.posonlyargs_annotations,
            *arguments.annotations,
            *arguments.kwonlyargs_annotations,
        ],
        strict=True,
    ):
        if argument.name == name:
            return annotation
    return None


def _name_annotations(node: nodes.Name) -> list[nodes.NodeNG]:
    """Return the annotations declared for *node* in the scope it is bound in."""
    scope, _ = node.lookup(node.name)
    annotations: list[nodes.NodeNG] = []
    # The declaration still applies when the name is reassigned later
    if isinstance(scope, nodes.FunctionDef | nodes.Lambda) and (
        annotation := _argument_annotation(scope.args, node.name)
    ):
        annotations.append(annotation)
    annotations.extend(
        ann_assign.annotation
        for ann_assign in scope.nodes_of_class(nodes.AnnAssign)
        if isinstance(ann_assign.target, nodes.AssignName)
        and ann_assign.target.name == node.name
        and ann_assign.target.scope() is scope
    )
    return annotations


class RuntimeDataTypedEntryChecker(BaseChecker):
    """Checker for setting ``runtime_data`` on an untyped ``ConfigEntry``."""

    name = "home_assistant_runtime_data_typed_entry"
    priority = -1
    msgs = {
        "W7460": (
            (
                "`%s` sets `runtime_data` but is annotated as a plain "
                "`ConfigEntry`, use a typed config entry instead"
            ),
            "home-assistant-runtime-data-untyped-config-entry",
            (
                "Used when `runtime_data` is set on a config entry that is "
                "annotated as a plain `ConfigEntry`. Define a typed config "
                "entry, such as `type MyConfigEntry = ConfigEntry[MyData]`, "
                "and use it in the annotation so `runtime_data` is typed."
            ),
        ),
    }
    options = ()

    _enabled = False
    _reported: set[nodes.NodeNG]

    def visit_module(self, node: nodes.Module) -> None:
        """Only check integration modules."""
        self._enabled = is_integration_module(node.name)
        self._reported = set()

    def visit_assignattr(self, node: nodes.AssignAttr) -> None:
        """Check ``<entry>.runtime_data = ...``."""
        if not self._enabled or node.attrname != "runtime_data":
            return
        if not isinstance(entry := node.expr, nodes.Name):
            return
        # entry.runtime_data: MyData declares a type without setting a value
        if isinstance(node.parent, nodes.AnnAssign) and node.parent.value is None:
            return

        for annotation in _name_annotations(entry):
            if annotation in self._reported or not _is_plain_config_entry(annotation):
                continue
            self._reported.add(annotation)
            self.add_message(
                "home-assistant-runtime-data-untyped-config-entry",
                node=annotation,
                args=(entry.name,),
            )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(RuntimeDataTypedEntryChecker(linter))
