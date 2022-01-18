"""Plugin for constructor definitions."""
from __future__ import annotations

from ast import arguments
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
    # TODO: add the correct message
    arg_types: dict[int, str]
    return_type: str | None
    disabled: bool = False


_MODULE_FILTERS: dict[str, re.Pattern] = {
    "init": re.compile(r"^homeassistant.components.[a-zA-Z_]+$"),
}

_METHOD_MATCH: list[TypeHintMatch] = [
    TypeHintMatch(
        module_filter=_MODULE_FILTERS["init"],
        function_name="setup",
        arg_types={0: "HomeAssistant", 1: "ConfigType"},
        return_type="bool",
    ),
    TypeHintMatch(
        module_filter=_MODULE_FILTERS["init"],
        function_name="async_setup",
        arg_types={0: "HomeAssistant", 1: "ConfigType"},
        return_type="bool",
    ),
    TypeHintMatch(
        module_filter=_MODULE_FILTERS["init"],
        function_name="async_setup_entry",
        arg_types={0: "HomeAssistant", 1: "ConfigEntry"},
        return_type="bool",
    ),
    TypeHintMatch(
        module_filter=_MODULE_FILTERS["init"],
        function_name="async_remove_entry",
        arg_types={0: "HomeAssistant", 1: "ConfigEntry"},
        return_type=None,
    ),
    TypeHintMatch(
        module_filter=_MODULE_FILTERS["init"],
        function_name="async_unload_entry",
        arg_types={0: "HomeAssistant", 1: "ConfigEntry"},
        return_type="bool",
    ),
    TypeHintMatch(
        module_filter=_MODULE_FILTERS["init"],
        function_name="async_migrate_entry",
        arg_types={0: "HomeAssistant", 1: "ConfigEntry"},
        return_type="bool",
    ),
]


class HassTypeHintChecker(BaseChecker):  # type: ignore[misc]
    """Checker for setup type hints."""

    __implements__ = IAstroidChecker

    name = "hass_enforce_type_hints"
    priority = -1
    msgs = {
        "W0020": (
            "First argument should be of type HomeAssistant",
            "hass-type-hint-hass",
            "Used when setup has some arguments typed but first isn't HomeAssistant",
        ),
        "W0021": (
            "Second argument should be of type ConfigType",
            "hass-type-hint-config-type",
            "Used when setup has some arguments typed but first isn't ConfigType",
        ),
        "W0022": (
            "Second argument should be of type ConfigEntry",
            "hass-type-hint-config-entry",
            "Used when setup has some arguments typed but first isn't ConfigEntry",
        ),
        "W0023": (
            "Return type should be of type bool",
            "hass-type-hint-return-bool",
            "Used when setup has some arguments typed but doesn't return bool",
        ),
        "W0024": (
            "First argument should be of type HomeAssistant",
            "hass-type-hint-return-none",
            "Used when setup has some arguments typed but doesn't return None",
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
        args = node.args
        annotations = (
            args.posonlyargs_annotations
            + args.annotations
            + args.kwonlyargs_annotations
        )
        if args.vararg is not None:
            annotations.append(args.varargannotation)
        if args.kwarg is not None:
            annotations.append(args.kwargannotation)
        if not [annotation for annotation in annotations if annotation is not None]:
            return

        # Check that all arguments are annotated.
        for key, value in match.arg_types.items():
            if (
                not isinstance(annotations[key], astroid.Name)
                or annotations[key].name != value
            ):
                # TODO: use the correct message
                # "hass-type-hint-config-entry"
                # "hass-type-hint-config-type"
                # "hass-type-hint-hass"
                self.add_message("hass-type-hint-hass", node=node)

        # Check the return type.
        if match.return_type is None:
            if (
                not isinstance(node.returns, astroid.Const)
                or node.returns.value is not None
            ):
                self.add_message("hass-type-hint-return-none", node=node)
        else:
            if (
                not isinstance(node.returns, astroid.Name)
                or node.returns.name != "bool"
            ):
                self.add_message("hass-type-hint-return-bool", node=node)


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassTypeHintChecker(linter))
