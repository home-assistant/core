"""Plugin for constructor definitions."""
from __future__ import annotations

from dataclasses import dataclass
import re

import astroid
from pylint.checkers import BaseChecker
from pylint.interfaces import IAstroidChecker
from pylint.lint import PyLinter


@dataclass
class TypeHintMatch:
    """Class for pattern matching."""

    module_filter: re.Pattern
    function_name: str
    arg_types: dict[int, TypeChecker]
    return_type: TypeChecker


@dataclass
class TypeChecker:
    """Class for pattern matching."""

    expected_type: str | None
    error_message: str

    def check(self, node: astroid.NodeNG) -> str | None:
        """Check"""
        if self.expected_type is None:
            if isinstance(node, astroid.Const) and node.value is None:
                return None
            return self.error_message
        if isinstance(node, astroid.Name) and node.name == self.expected_type:
            return None
        return self.error_message


_MODULE_FILTERS: dict[str, re.Pattern] = {
    "init": re.compile(r"^homeassistant.components.[a-zA-Z_]+$"),
}

_ARGUMENT_MATCH: dict[str, TypeChecker] = {
    "HomeAssistant": TypeChecker("HomeAssistant", "hass-type-hint-hass"),
    "ConfigType": TypeChecker("ConfigType", "hass-type-hint-config-type"),
    "ConfigEntry": TypeChecker("ConfigEntry", "hass-type-hint-config-entry"),
}
_RETURN_MATCH: dict[str, TypeChecker] = {
    "bool": TypeChecker("bool", "hass-type-hint-return-bool"),
    "None": TypeChecker(None, "hass-type-hint-return-none"),
}

_METHOD_MATCH: list[TypeHintMatch] = [
    TypeHintMatch(
        module_filter=_MODULE_FILTERS["init"],
        function_name="setup",
        arg_types={
            0: _ARGUMENT_MATCH["HomeAssistant"],
            1: _ARGUMENT_MATCH["ConfigType"],
        },
        return_type=_RETURN_MATCH["bool"],
    ),
    TypeHintMatch(
        module_filter=_MODULE_FILTERS["init"],
        function_name="async_setup",
        arg_types={
            0: _ARGUMENT_MATCH["HomeAssistant"],
            1: _ARGUMENT_MATCH["ConfigType"],
        },
        return_type=_RETURN_MATCH["bool"],
    ),
    TypeHintMatch(
        module_filter=_MODULE_FILTERS["init"],
        function_name="async_setup_entry",
        arg_types={
            0: _ARGUMENT_MATCH["HomeAssistant"],
            1: _ARGUMENT_MATCH["ConfigEntry"],
        },
        return_type=_RETURN_MATCH["bool"],
    ),
    TypeHintMatch(
        module_filter=_MODULE_FILTERS["init"],
        function_name="async_remove_entry",
        arg_types={
            0: _ARGUMENT_MATCH["HomeAssistant"],
            1: _ARGUMENT_MATCH["ConfigEntry"],
        },
        return_type=_RETURN_MATCH["None"],
    ),
    TypeHintMatch(
        module_filter=_MODULE_FILTERS["init"],
        function_name="async_unload_entry",
        arg_types={
            0: _ARGUMENT_MATCH["HomeAssistant"],
            1: _ARGUMENT_MATCH["ConfigEntry"],
        },
        return_type=_RETURN_MATCH["bool"],
    ),
    TypeHintMatch(
        module_filter=_MODULE_FILTERS["init"],
        function_name="async_migrate_entry",
        arg_types={
            0: _ARGUMENT_MATCH["HomeAssistant"],
            1: _ARGUMENT_MATCH["ConfigEntry"],
        },
        return_type=_RETURN_MATCH["bool"],
    ),
]


def _get_all_annotation(node: astroid.FunctionDef) -> list[astroid.NodeNG | None]:
    args = node.args
    annotations = (
        args.posonlyargs_annotations + args.annotations + args.kwonlyargs_annotations
    )
    if args.vararg is not None:
        annotations.append(args.varargannotation)
    if args.kwarg is not None:
        annotations.append(args.kwargannotation)
    return annotations


def _has_valid_annotations(
    annotations: list[astroid.NodeNG | None],
) -> list[astroid.NodeNG | None]:
    for annotation in annotations:
        if annotation is not None:
            return True
    return False


class HassTypeHintChecker(BaseChecker):  # type: ignore[misc]
    """Checker for setup type hints."""

    __implements__ = IAstroidChecker

    name = "hass_enforce_type_hints"
    priority = -1
    msgs = {
        "W0020": (
            "Argument should be of type HomeAssistant",
            "hass-type-hint-hass",
            "Used when method argument isn't HomeAssistant as expected",
        ),
        "W0021": (
            "Argument should be of type ConfigType",
            "hass-type-hint-config-type",
            "Used when method argument isn't ConfigType as expected",
        ),
        "W0022": (
            "Argument should be of type ConfigEntry",
            "hass-type-hint-config-entry",
            "Used when method argument isn't ConfigEntry as expected",
        ),
        "W0023": (
            "Return type should be of type bool",
            "hass-type-hint-return-bool",
            "Used when method return type isn't bool",
        ),
        "W0024": (
            "Return type should be None",
            "hass-type-hint-return-none",
            "Used when method return type isn't None",
        ),
    }
    options = ()

    def __init__(self, linter: PyLinter | None = None) -> None:
        super().__init__(linter)
        self.current_package: str | None = None
        self.module: str | None = None

    def visit_module(self, node: astroid.Module) -> None:
        """Called when a Module node is visited."""
        self.module = node.name
        if node.package:
            self.current_package = node.name
        else:
            # Strip name of the current module
            self.current_package = node.name[: node.name.rfind(".")]

    def visit_functiondef(self, node: astroid.FunctionDef) -> None:
        """Called when a FunctionDef node is visited."""
        for match in _METHOD_MATCH:
            self._visit_functiondef(node, match)

    def _visit_functiondef(
        self, node: astroid.FunctionDef, match: TypeHintMatch
    ) -> None:
        if node.name != match.function_name:
            return
        if node.is_method():
            return
        if not match.module_filter.match(self.module):
            return

        # Check that at least one argument is annotated.
        annotations = _get_all_annotation(node)
        if node.returns is None and not _has_valid_annotations(annotations):
            return

        # Check that all arguments are annotated.
        for key, value in match.arg_types.items():
            if message := value.check(annotations[key]):
                self.add_message(message, node=node)

        # Check the return type.
        if message := match.return_type.check(node.returns):
            self.add_message(message, node=node)


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassTypeHintChecker(linter))
