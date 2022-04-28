"""Plugin to enforce type hints on specific functions."""
from __future__ import annotations

from dataclasses import dataclass
import re

import astroid
from pylint.checkers import BaseChecker
from pylint.interfaces import IAstroidChecker
from pylint.lint import PyLinter

from homeassistant.const import Platform

UNDEFINED = object()


@dataclass
class TypeHintMatch:
    """Class for pattern matching."""

    module_filter: re.Pattern
    function_name: str
    arg_types: dict[int, str]
    return_type: list[str] | str | None


_TYPE_HINT_MATCHERS: dict[str, re.Pattern] = {
    # a_or_b matches items such as "DiscoveryInfoType | None"
    "a_or_b": re.compile(r"^(\w+) \| (\w+)$"),
    # x_of_y matches items such as "Awaitable[None]"
    "x_of_y": re.compile(r"^(\w+)\[(.*?]*)\]$"),
    # x_of_y_comma_z matches items such as "Callable[..., Awaitable[None]]"
    "x_of_y_comma_z": re.compile(r"^(\w+)\[(.*?]*), (.*?]*)\]$"),
}

_MODULE_FILTERS: dict[str, re.Pattern] = {
    # init matches only in the package root (__init__.py)
    "init": re.compile(r"^homeassistant\.components\.\w+$"),
    # any_platform matches any platform in the package root ({platform}.py)
    "any_platform": re.compile(
        f"^homeassistant\\.components\\.\\w+\\.({'|'.join([platform.value for platform in Platform])})$"
    ),
    # device_tracker matches only in the package root (device_tracker.py)
    "device_tracker": re.compile(r"^homeassistant\.components\.\w+\.(device_tracker)$"),
    # diagnostics matches only in the package root (diagnostics.py)
    "diagnostics": re.compile(r"^homeassistant\.components\.\w+\.(diagnostics)$"),
    # config_flow matches only in the package root (config_flow.py)
    "config_flow": re.compile(r"^homeassistant\.components\.\w+\.(config_flow)$")
}

_METHOD_MATCH: list[TypeHintMatch] = [
    TypeHintMatch(
        module_filter=_MODULE_FILTERS["init"],
        function_name="setup",
        arg_types={
            0: "HomeAssistant",
            1: "ConfigType",
        },
        return_type="bool",
    ),
    TypeHintMatch(
        module_filter=_MODULE_FILTERS["init"],
        function_name="async_setup",
        arg_types={
            0: "HomeAssistant",
            1: "ConfigType",
        },
        return_type="bool",
    ),
    TypeHintMatch(
        module_filter=_MODULE_FILTERS["init"],
        function_name="async_setup_entry",
        arg_types={
            0: "HomeAssistant",
            1: "ConfigEntry",
        },
        return_type="bool",
    ),
    TypeHintMatch(
        module_filter=_MODULE_FILTERS["init"],
        function_name="async_remove_entry",
        arg_types={
            0: "HomeAssistant",
            1: "ConfigEntry",
        },
        return_type=None,
    ),
    TypeHintMatch(
        module_filter=_MODULE_FILTERS["init"],
        function_name="async_unload_entry",
        arg_types={
            0: "HomeAssistant",
            1: "ConfigEntry",
        },
        return_type="bool",
    ),
    TypeHintMatch(
        module_filter=_MODULE_FILTERS["init"],
        function_name="async_migrate_entry",
        arg_types={
            0: "HomeAssistant",
            1: "ConfigEntry",
        },
        return_type="bool",
    ),
    TypeHintMatch(
        module_filter=_MODULE_FILTERS["any_platform"],
        function_name="setup_platform",
        arg_types={
            0: "HomeAssistant",
            1: "ConfigType",
            2: "AddEntitiesCallback",
            3: "DiscoveryInfoType | None",
        },
        return_type=None,
    ),
    TypeHintMatch(
        module_filter=_MODULE_FILTERS["any_platform"],
        function_name="async_setup_platform",
        arg_types={
            0: "HomeAssistant",
            1: "ConfigType",
            2: "AddEntitiesCallback",
            3: "DiscoveryInfoType | None",
        },
        return_type=None,
    ),
    TypeHintMatch(
        module_filter=_MODULE_FILTERS["any_platform"],
        function_name="async_setup_entry",
        arg_types={
            0: "HomeAssistant",
            1: "ConfigEntry",
            2: "AddEntitiesCallback",
        },
        return_type=None,
    ),
    TypeHintMatch(
        module_filter=_MODULE_FILTERS["device_tracker"],
        function_name="setup_scanner",
        arg_types={
            0: "HomeAssistant",
            1: "ConfigType",
            2: "Callable[..., None]",
            3: "DiscoveryInfoType | None",
        },
        return_type="bool",
    ),
    TypeHintMatch(
        module_filter=_MODULE_FILTERS["device_tracker"],
        function_name="async_setup_scanner",
        arg_types={
            0: "HomeAssistant",
            1: "ConfigType",
            2: "Callable[..., Awaitable[None]]",
            3: "DiscoveryInfoType | None",
        },
        return_type="bool",
    ),
    TypeHintMatch(
        module_filter=_MODULE_FILTERS["device_tracker"],
        function_name="get_scanner",
        arg_types={
            0: "HomeAssistant",
            1: "ConfigType",
        },
        return_type=["DeviceScanner", "DeviceScanner | None"],
    ),
    TypeHintMatch(
        module_filter=_MODULE_FILTERS["device_tracker"],
        function_name="async_get_scanner",
        arg_types={
            0: "HomeAssistant",
            1: "ConfigType",
        },
        return_type=["DeviceScanner", "DeviceScanner | None"],
    ),
    TypeHintMatch(
        module_filter=_MODULE_FILTERS["diagnostics"],
        function_name="async_get_config_entry_diagnostics",
        arg_types={
            0: "HomeAssistant",
            1: "ConfigEntry",
        },
        return_type=UNDEFINED,
    ),
    TypeHintMatch(
        module_filter=_MODULE_FILTERS["diagnostics"],
        function_name="async_get_device_diagnostics",
        arg_types={
            0: "HomeAssistant",
            1: "ConfigEntry",
            2: "DeviceEntry",
        },
        return_type=UNDEFINED,
    ),
    TypeHintMatch(
        module_filter=_MODULE_FILTERS["config_flow"],
        function_name="_async_has_devices",
        arg_types={
            0: "HomeAssistant",
        },
        return_type="bool",
    ),
]


def _is_valid_type(expected_type: list[str] | str | None, node: astroid.NodeNG) -> bool:
    """Check the argument node against the expected type."""
    if expected_type is UNDEFINED:
        return True

    if isinstance(expected_type, list):
        for expected_type_item in expected_type:
            if _is_valid_type(expected_type_item, node):
                return True
        return False

    # Const occurs when the type is None
    if expected_type is None or expected_type == "None":
        return isinstance(node, astroid.Const) and node.value is None

    # Const occurs when the type is an Ellipsis
    if expected_type == "...":
        return isinstance(node, astroid.Const) and node.value == Ellipsis

    # Special case for `xxx | yyy`
    if match := _TYPE_HINT_MATCHERS["a_or_b"].match(expected_type):
        return (
            isinstance(node, astroid.BinOp)
            and _is_valid_type(match.group(1), node.left)
            and _is_valid_type(match.group(2), node.right)
        )

    # Special case for xxx[yyy, zzz]`
    if match := _TYPE_HINT_MATCHERS["x_of_y_comma_z"].match(expected_type):
        return (
            isinstance(node, astroid.Subscript)
            and _is_valid_type(match.group(1), node.value)
            and isinstance(node.slice, astroid.Tuple)
            and _is_valid_type(match.group(2), node.slice.elts[0])
            and _is_valid_type(match.group(3), node.slice.elts[1])
        )

    # Special case for xxx[yyy]`
    if match := _TYPE_HINT_MATCHERS["x_of_y"].match(expected_type):
        return (
            isinstance(node, astroid.Subscript)
            and _is_valid_type(match.group(1), node.value)
            and _is_valid_type(match.group(2), node.slice)
        )

    # Name occurs when a namespace is not used, eg. "HomeAssistant"
    if isinstance(node, astroid.Name) and node.name == expected_type:
        return True

    # Attribute occurs when a namespace is used, eg. "core.HomeAssistant"
    return isinstance(node, astroid.Attribute) and node.attrname == expected_type


def _get_all_annotations(node: astroid.FunctionDef) -> list[astroid.NodeNG | None]:
    args = node.args
    annotations: list[astroid.NodeNG | None] = (
        args.posonlyargs_annotations + args.annotations + args.kwonlyargs_annotations
    )
    if args.vararg is not None:
        annotations.append(args.varargannotation)
    if args.kwarg is not None:
        annotations.append(args.kwargannotation)
    return annotations


def _has_valid_annotations(
    annotations: list[astroid.NodeNG | None],
) -> bool:
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
            "Argument %d should be of type %s",
            "hass-argument-type",
            "Used when method argument type is incorrect",
        ),
        "W0021": (
            "Return type should be %s",
            "hass-return-type",
            "Used when method return type is incorrect",
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

    def visit_asyncfunctiondef(self, node: astroid.AsyncFunctionDef) -> None:
        """Called when an AsyncFunctionDef node is visited."""
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
        annotations = _get_all_annotations(node)
        if node.returns is None and not _has_valid_annotations(annotations):
            return

        # Check that all arguments are correctly annotated.
        for key, expected_type in match.arg_types.items():
            if not _is_valid_type(expected_type, annotations[key]):
                self.add_message(
                    "hass-argument-type",
                    node=node.args.args[key],
                    args=(key + 1, expected_type),
                )

        # Check the return type.
        if not _is_valid_type(return_type := match.return_type, node.returns):
            self.add_message("hass-return-type", node=node, args=return_type or "None")


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassTypeHintChecker(linter))
