"""Checker for plain ``ConfigEntry`` annotations in integrations with a typed one.

When an integration defines a typed config entry, such as
``type MyConfigEntry = ConfigEntry[MyData]``, it should use that type
everywhere it handles its own config entry, so ``entry.runtime_data`` stays
typed. A plain ``ConfigEntry`` loses that.

``config_flow.py`` is not checked for now.

``W7460`` (``home-assistant-use-typed-config-entry``)
"""

from collections.abc import Iterator
from pathlib import Path

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.const import Module
from pylint_home_assistant.helpers.config_entry import (
    is_config_entry,
    typed_config_entries,
)
from pylint_home_assistant.helpers.integration import get_integration_dir
from pylint_home_assistant.helpers.module_info import parse_module


def _plain_config_entries(annotation: nodes.NodeNG) -> Iterator[nodes.NodeNG]:
    """Yield each ``ConfigEntry`` in an annotation that has no type arguments."""
    if is_config_entry(annotation):
        yield annotation
        return
    match annotation:
        # ConfigEntry[...] is already typed, but its arguments are not checked
        case nodes.Subscript(value=value) if is_config_entry(value):
            return
        case nodes.Subscript(slice=slice_):
            yield from _plain_config_entries(slice_)
        case nodes.BinOp(op="|", left=left, right=right):
            yield from _plain_config_entries(left)
            yield from _plain_config_entries(right)
        case nodes.Tuple(elts=elts):
            for elt in elts:
                yield from _plain_config_entries(elt)


def _function_annotations(node: nodes.FunctionDef) -> Iterator[nodes.NodeNG]:
    """Yield the argument and return annotations of a function."""
    arguments = node.args
    yield from (
        annotation
        for annotation in (
            *arguments.posonlyargs_annotations,
            *arguments.annotations,
            *arguments.kwonlyargs_annotations,
            arguments.varargannotation,
            arguments.kwargannotation,
            node.returns,
        )
        if annotation is not None
    )


class HassTypedConfigEntryChecker(BaseChecker):
    """Checker for plain ``ConfigEntry`` annotations."""

    name = "home_assistant_typed_config_entry"
    priority = -1
    msgs = {
        "W7460": (
            "Use the integration's typed config entry (%s) instead of `ConfigEntry`",
            "home-assistant-use-typed-config-entry",
            (
                "Used when an integration that defines a typed config entry, "
                "such as `type MyConfigEntry = ConfigEntry[MyData]`, annotates "
                "a config entry as a plain `ConfigEntry`."
            ),
        ),
    }
    options = ()

    _typed_entries: tuple[str, ...] = ()

    def visit_module(self, node: nodes.Module) -> None:
        """Look up the typed config entries of the integration."""
        self._typed_entries = ()
        parsed = parse_module(node.name)
        if parsed is None or parsed.module == Module.CONFIG_FLOW:
            return
        integration_dir: Path | None = get_integration_dir(node)
        if integration_dir is not None:
            self._typed_entries = typed_config_entries(integration_dir)

    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        """Check argument and return annotations."""
        if self._typed_entries:
            for annotation in _function_annotations(node):
                self._check_annotation(annotation)

    visit_asyncfunctiondef = visit_functiondef

    def visit_annassign(self, node: nodes.AnnAssign) -> None:
        """Check variable and attribute annotations."""
        if self._typed_entries:
            self._check_annotation(node.annotation)

    def _check_annotation(self, annotation: nodes.NodeNG) -> None:
        for plain in _plain_config_entries(annotation):
            self.add_message(
                "home-assistant-use-typed-config-entry",
                node=plain,
                args=(", ".join(f"`{name}`" for name in self._typed_entries),),
            )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassTypedConfigEntryChecker(linter))
