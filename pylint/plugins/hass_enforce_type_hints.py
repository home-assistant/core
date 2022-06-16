"""Plugin to enforce type hints on specific functions."""
from __future__ import annotations

from dataclasses import dataclass
import re

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from homeassistant.const import Platform

UNDEFINED = object()

_PLATFORMS: set[str] = {platform.value for platform in Platform}


@dataclass
class TypeHintMatch:
    """Class for pattern matching."""

    function_name: str
    arg_types: dict[int, str]
    return_type: list[str] | str | None | object
    check_return_type_inheritance: bool = False


@dataclass
class ClassTypeHintMatch:
    """Class for pattern matching."""

    base_class: str
    matches: list[TypeHintMatch]


_TYPE_HINT_MATCHERS: dict[str, re.Pattern[str]] = {
    # a_or_b matches items such as "DiscoveryInfoType | None"
    "a_or_b": re.compile(r"^(\w+) \| (\w+)$"),
    # x_of_y matches items such as "Awaitable[None]"
    "x_of_y": re.compile(r"^(\w+)\[(.*?]*)\]$"),
    # x_of_y_comma_z matches items such as "Callable[..., Awaitable[None]]"
    "x_of_y_comma_z": re.compile(r"^(\w+)\[(.*?]*), (.*?]*)\]$"),
    # x_of_y_of_z_comma_a matches items such as "list[dict[str, Any]]"
    "x_of_y_of_z_comma_a": re.compile(r"^(\w+)\[(\w+)\[(.*?]*), (.*?]*)\]\]$"),
}

_MODULE_REGEX: re.Pattern[str] = re.compile(r"^homeassistant\.components\.\w+(\.\w+)?$")

_FUNCTION_MATCH: dict[str, list[TypeHintMatch]] = {
    "__init__": [
        TypeHintMatch(
            function_name="setup",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigType",
            },
            return_type="bool",
        ),
        TypeHintMatch(
            function_name="async_setup",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigType",
            },
            return_type="bool",
        ),
        TypeHintMatch(
            function_name="async_setup_entry",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigEntry",
            },
            return_type="bool",
        ),
        TypeHintMatch(
            function_name="async_remove_entry",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigEntry",
            },
            return_type=None,
        ),
        TypeHintMatch(
            function_name="async_unload_entry",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigEntry",
            },
            return_type="bool",
        ),
        TypeHintMatch(
            function_name="async_migrate_entry",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigEntry",
            },
            return_type="bool",
        ),
        TypeHintMatch(
            function_name="async_remove_config_entry_device",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigEntry",
                2: "DeviceEntry",
            },
            return_type="bool",
        ),
    ],
    "__any_platform__": [
        TypeHintMatch(
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
            function_name="async_setup_entry",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigEntry",
                2: "AddEntitiesCallback",
            },
            return_type=None,
        ),
    ],
    "application_credentials": [
        TypeHintMatch(
            function_name="async_get_auth_implementation",
            arg_types={
                0: "HomeAssistant",
                1: "str",
                2: "ClientCredential",
            },
            return_type="AbstractOAuth2Implementation",
        ),
        TypeHintMatch(
            function_name="async_get_authorization_server",
            arg_types={
                0: "HomeAssistant",
            },
            return_type="AuthorizationServer",
        ),
    ],
    "backup": [
        TypeHintMatch(
            function_name="async_pre_backup",
            arg_types={
                0: "HomeAssistant",
            },
            return_type=None,
        ),
        TypeHintMatch(
            function_name="async_post_backup",
            arg_types={
                0: "HomeAssistant",
            },
            return_type=None,
        ),
    ],
    "cast": [
        TypeHintMatch(
            function_name="async_get_media_browser_root_object",
            arg_types={
                0: "HomeAssistant",
                1: "str",
            },
            return_type="list[BrowseMedia]",
        ),
        TypeHintMatch(
            function_name="async_browse_media",
            arg_types={
                0: "HomeAssistant",
                1: "str",
                2: "str",
                3: "str",
            },
            return_type=["BrowseMedia", "BrowseMedia | None"],
        ),
        TypeHintMatch(
            function_name="async_play_media",
            arg_types={
                0: "HomeAssistant",
                1: "str",
                2: "Chromecast",
                3: "str",
                4: "str",
            },
            return_type="bool",
        ),
    ],
    "config_flow": [
        TypeHintMatch(
            function_name="_async_has_devices",
            arg_types={
                0: "HomeAssistant",
            },
            return_type="bool",
        ),
    ],
    "device_action": [
        TypeHintMatch(
            function_name="async_validate_action_config",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigType",
            },
            return_type="ConfigType",
        ),
        TypeHintMatch(
            function_name="async_call_action_from_config",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigType",
                2: "TemplateVarsType",
                3: "Context | None",
            },
            return_type=None,
        ),
        TypeHintMatch(
            function_name="async_get_action_capabilities",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigType",
            },
            return_type="dict[str, Schema]",
        ),
        TypeHintMatch(
            function_name="async_get_actions",
            arg_types={
                0: "HomeAssistant",
                1: "str",
            },
            return_type=["list[dict[str, str]]", "list[dict[str, Any]]"],
        ),
    ],
    "device_condition": [
        TypeHintMatch(
            function_name="async_validate_condition_config",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigType",
            },
            return_type="ConfigType",
        ),
        TypeHintMatch(
            function_name="async_condition_from_config",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigType",
            },
            return_type="ConditionCheckerType",
        ),
        TypeHintMatch(
            function_name="async_get_condition_capabilities",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigType",
            },
            return_type="dict[str, Schema]",
        ),
        TypeHintMatch(
            function_name="async_get_conditions",
            arg_types={
                0: "HomeAssistant",
                1: "str",
            },
            return_type=["list[dict[str, str]]", "list[dict[str, Any]]"],
        ),
    ],
    "device_tracker": [
        TypeHintMatch(
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
            function_name="get_scanner",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigType",
            },
            return_type=["DeviceScanner", "DeviceScanner | None"],
        ),
        TypeHintMatch(
            function_name="async_get_scanner",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigType",
            },
            return_type=["DeviceScanner", "DeviceScanner | None"],
        ),
    ],
    "device_trigger": [
        TypeHintMatch(
            function_name="async_validate_condition_config",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigType",
            },
            return_type="ConfigType",
        ),
        TypeHintMatch(
            function_name="async_attach_trigger",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigType",
                2: "AutomationActionType",
                3: "AutomationTriggerInfo",
            },
            return_type="CALLBACK_TYPE",
        ),
        TypeHintMatch(
            function_name="async_get_trigger_capabilities",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigType",
            },
            return_type="dict[str, Schema]",
        ),
        TypeHintMatch(
            function_name="async_get_triggers",
            arg_types={
                0: "HomeAssistant",
                1: "str",
            },
            return_type=["list[dict[str, str]]", "list[dict[str, Any]]"],
        ),
    ],
    "diagnostics": [
        TypeHintMatch(
            function_name="async_get_config_entry_diagnostics",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigEntry",
            },
            return_type=UNDEFINED,
        ),
        TypeHintMatch(
            function_name="async_get_device_diagnostics",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigEntry",
                2: "DeviceEntry",
            },
            return_type=UNDEFINED,
        ),
    ],
}

_CLASS_MATCH: dict[str, list[ClassTypeHintMatch]] = {
    "config_flow": [
        ClassTypeHintMatch(
            base_class="ConfigFlow",
            matches=[
                TypeHintMatch(
                    function_name="async_get_options_flow",
                    arg_types={
                        0: "ConfigEntry",
                    },
                    return_type="OptionsFlow",
                    check_return_type_inheritance=True,
                ),
                TypeHintMatch(
                    function_name="async_step_dhcp",
                    arg_types={
                        1: "DhcpServiceInfo",
                    },
                    return_type="FlowResult",
                ),
                TypeHintMatch(
                    function_name="async_step_hassio",
                    arg_types={
                        1: "HassioServiceInfo",
                    },
                    return_type="FlowResult",
                ),
                TypeHintMatch(
                    function_name="async_step_homekit",
                    arg_types={
                        1: "ZeroconfServiceInfo",
                    },
                    return_type="FlowResult",
                ),
                TypeHintMatch(
                    function_name="async_step_mqtt",
                    arg_types={
                        1: "MqttServiceInfo",
                    },
                    return_type="FlowResult",
                ),
                TypeHintMatch(
                    function_name="async_step_ssdp",
                    arg_types={
                        1: "SsdpServiceInfo",
                    },
                    return_type="FlowResult",
                ),
                TypeHintMatch(
                    function_name="async_step_usb",
                    arg_types={
                        1: "UsbServiceInfo",
                    },
                    return_type="FlowResult",
                ),
                TypeHintMatch(
                    function_name="async_step_zeroconf",
                    arg_types={
                        1: "ZeroconfServiceInfo",
                    },
                    return_type="FlowResult",
                ),
            ],
        ),
    ]
}


def _is_valid_type(
    expected_type: list[str] | str | None | object, node: nodes.NodeNG
) -> bool:
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
        return isinstance(node, nodes.Const) and node.value is None

    assert isinstance(expected_type, str)

    # Const occurs when the type is an Ellipsis
    if expected_type == "...":
        return isinstance(node, nodes.Const) and node.value == Ellipsis

    # Special case for `xxx | yyy`
    if match := _TYPE_HINT_MATCHERS["a_or_b"].match(expected_type):
        return (
            isinstance(node, nodes.BinOp)
            and _is_valid_type(match.group(1), node.left)
            and _is_valid_type(match.group(2), node.right)
        )

    # Special case for xxx[yyy[zzz, aaa]]`
    if match := _TYPE_HINT_MATCHERS["x_of_y_of_z_comma_a"].match(expected_type):
        return (
            isinstance(node, nodes.Subscript)
            and _is_valid_type(match.group(1), node.value)
            and isinstance(subnode := node.slice, nodes.Subscript)
            and _is_valid_type(match.group(2), subnode.value)
            and isinstance(subnode.slice, nodes.Tuple)
            and _is_valid_type(match.group(3), subnode.slice.elts[0])
            and _is_valid_type(match.group(4), subnode.slice.elts[1])
        )

    # Special case for xxx[yyy, zzz]`
    if match := _TYPE_HINT_MATCHERS["x_of_y_comma_z"].match(expected_type):
        return (
            isinstance(node, nodes.Subscript)
            and _is_valid_type(match.group(1), node.value)
            and isinstance(node.slice, nodes.Tuple)
            and _is_valid_type(match.group(2), node.slice.elts[0])
            and _is_valid_type(match.group(3), node.slice.elts[1])
        )

    # Special case for xxx[yyy]`
    if match := _TYPE_HINT_MATCHERS["x_of_y"].match(expected_type):
        return (
            isinstance(node, nodes.Subscript)
            and _is_valid_type(match.group(1), node.value)
            and _is_valid_type(match.group(2), node.slice)
        )

    # Name occurs when a namespace is not used, eg. "HomeAssistant"
    if isinstance(node, nodes.Name) and node.name == expected_type:
        return True

    # Attribute occurs when a namespace is used, eg. "core.HomeAssistant"
    return isinstance(node, nodes.Attribute) and node.attrname == expected_type


def _is_valid_return_type(match: TypeHintMatch, node: nodes.NodeNG) -> bool:
    if _is_valid_type(match.return_type, node):
        return True

    if isinstance(node, nodes.BinOp):
        return _is_valid_return_type(match, node.left) and _is_valid_return_type(
            match, node.right
        )

    if (
        match.check_return_type_inheritance
        and isinstance(match.return_type, str)
        and isinstance(node, nodes.Name)
    ):
        ancestor: nodes.ClassDef
        for infer_node in node.infer():
            if isinstance(infer_node, nodes.ClassDef):
                if infer_node.name == match.return_type:
                    return True
                for ancestor in infer_node.ancestors():
                    if ancestor.name == match.return_type:
                        return True

    return False


def _get_all_annotations(node: nodes.FunctionDef) -> list[nodes.NodeNG | None]:
    args = node.args
    annotations: list[nodes.NodeNG | None] = (
        args.posonlyargs_annotations + args.annotations + args.kwonlyargs_annotations
    )
    if args.vararg is not None:
        annotations.append(args.varargannotation)
    if args.kwarg is not None:
        annotations.append(args.kwargannotation)
    return annotations


def _has_valid_annotations(
    annotations: list[nodes.NodeNG | None],
) -> bool:
    for annotation in annotations:
        if annotation is not None:
            return True
    return False


def _get_module_platform(module_name: str) -> str | None:
    """Called when a Module node is visited."""
    if not (module_match := _MODULE_REGEX.match(module_name)):
        # Ensure `homeassistant.components.<component>`
        # Or `homeassistant.components.<component>.<platform>`
        return None

    platform = module_match.groups()[0]
    return platform.lstrip(".") if platform else "__init__"


class HassTypeHintChecker(BaseChecker):  # type: ignore[misc]
    """Checker for setup type hints."""

    name = "hass_enforce_type_hints"
    priority = -1
    msgs = {
        "W7431": (
            "Argument %d should be of type %s",
            "hass-argument-type",
            "Used when method argument type is incorrect",
        ),
        "W7432": (
            "Return type should be %s",
            "hass-return-type",
            "Used when method return type is incorrect",
        ),
    }
    options = (
        (
            "ignore-missing-annotations",
            {
                "default": True,
                "type": "yn",
                "metavar": "<y or n>",
                "help": "Set to ``no`` if you wish to check functions that do not "
                "have any type hints.",
            },
        ),
    )

    def __init__(self, linter: PyLinter | None = None) -> None:
        super().__init__(linter)
        self._function_matchers: list[TypeHintMatch] = []
        self._class_matchers: list[ClassTypeHintMatch] = []

    def visit_module(self, node: nodes.Module) -> None:
        """Called when a Module node is visited."""
        self._function_matchers = []
        self._class_matchers = []

        if (module_platform := _get_module_platform(node.name)) is None:
            return

        if module_platform in _PLATFORMS:
            self._function_matchers.extend(_FUNCTION_MATCH["__any_platform__"])

        if function_matches := _FUNCTION_MATCH.get(module_platform):
            self._function_matchers.extend(function_matches)

        if class_matches := _CLASS_MATCH.get(module_platform):
            self._class_matchers = class_matches

    def visit_classdef(self, node: nodes.ClassDef) -> None:
        """Called when a ClassDef node is visited."""
        ancestor: nodes.ClassDef
        for ancestor in node.ancestors():
            for class_matches in self._class_matchers:
                if ancestor.name == class_matches.base_class:
                    self._visit_class_functions(node, class_matches.matches)

    def _visit_class_functions(
        self, node: nodes.ClassDef, matches: list[TypeHintMatch]
    ) -> None:
        for match in matches:
            for function_node in node.mymethods():
                function_name: str | None = function_node.name
                if match.function_name == function_name:
                    self._check_function(function_node, match)

    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        """Called when a FunctionDef node is visited."""
        for match in self._function_matchers:
            if node.name != match.function_name or node.is_method():
                continue
            self._check_function(node, match)

    visit_asyncfunctiondef = visit_functiondef

    def _check_function(self, node: nodes.FunctionDef, match: TypeHintMatch) -> None:
        # Check that at least one argument is annotated.
        annotations = _get_all_annotations(node)
        if (
            self.linter.config.ignore_missing_annotations
            and node.returns is None
            and not _has_valid_annotations(annotations)
        ):
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
        if not _is_valid_return_type(match, node.returns):
            self.add_message(
                "hass-return-type", node=node, args=match.return_type or "None"
            )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassTypeHintChecker(linter))
