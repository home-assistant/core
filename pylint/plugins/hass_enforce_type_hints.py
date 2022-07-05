"""Plugin to enforce type hints on specific functions."""
from __future__ import annotations

from dataclasses import dataclass
import re

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from homeassistant.const import Platform

DEVICE_CLASS = object()
UNDEFINED = object()

_PLATFORMS: set[str] = {platform.value for platform in Platform}


@dataclass
class TypeHintMatch:
    """Class for pattern matching."""

    function_name: str
    return_type: list[str] | str | None | object
    arg_types: dict[int, str] | None = None
    """arg_types is for positional arguments"""
    named_arg_types: dict[str, str] | None = None
    """named_arg_types is for named or keyword arguments"""
    kwargs_type: str | None = None
    """kwargs_type is for the special case `**kwargs`"""
    check_return_type_inheritance: bool = False
    has_async_counterpart: bool = False

    def need_to_check_function(self, node: nodes.FunctionDef) -> bool:
        """Confirm if function should be checked."""
        return (
            self.function_name == node.name
            or self.has_async_counterpart
            and node.name == f"async_{self.function_name}"
            or self.function_name.endswith("*")
            and node.name.startswith(self.function_name[:-1])
        )


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
            has_async_counterpart=True,
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
            has_async_counterpart=True,
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
            has_async_counterpart=True,
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
            base_class="FlowHandler",
            matches=[
                TypeHintMatch(
                    function_name="async_step_*",
                    arg_types={},
                    return_type="FlowResult",
                ),
            ],
        ),
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
                    function_name="async_step_reauth",
                    arg_types={
                        1: "Mapping[str, Any]",
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
    ],
}
# Overriding properties and functions are normally checked by mypy, and will only
# be checked by pylint when --ignore-missing-annotations is False
_ENTITY_MATCH: list[TypeHintMatch] = [
    TypeHintMatch(
        function_name="should_poll",
        return_type="bool",
    ),
    TypeHintMatch(
        function_name="unique_id",
        return_type=["str", None],
    ),
    TypeHintMatch(
        function_name="name",
        return_type=["str", None],
    ),
    TypeHintMatch(
        function_name="state",
        return_type=["StateType", None, "str", "int", "float"],
    ),
    TypeHintMatch(
        function_name="capability_attributes",
        return_type=["Mapping[str, Any]", None],
    ),
    TypeHintMatch(
        function_name="state_attributes",
        return_type=["dict[str, Any]", None],
    ),
    TypeHintMatch(
        function_name="device_state_attributes",
        return_type=["Mapping[str, Any]", None],
    ),
    TypeHintMatch(
        function_name="extra_state_attributes",
        return_type=["Mapping[str, Any]", None],
    ),
    TypeHintMatch(
        function_name="device_info",
        return_type=["DeviceInfo", None],
    ),
    TypeHintMatch(
        function_name="device_class",
        return_type=[DEVICE_CLASS, "str", None],
    ),
    TypeHintMatch(
        function_name="unit_of_measurement",
        return_type=["str", None],
    ),
    TypeHintMatch(
        function_name="icon",
        return_type=["str", None],
    ),
    TypeHintMatch(
        function_name="entity_picture",
        return_type=["str", None],
    ),
    TypeHintMatch(
        function_name="available",
        return_type="bool",
    ),
    TypeHintMatch(
        function_name="assumed_state",
        return_type="bool",
    ),
    TypeHintMatch(
        function_name="force_update",
        return_type="bool",
    ),
    TypeHintMatch(
        function_name="supported_features",
        return_type=["int", None],
    ),
    TypeHintMatch(
        function_name="context_recent_time",
        return_type="timedelta",
    ),
    TypeHintMatch(
        function_name="entity_registry_enabled_default",
        return_type="bool",
    ),
    TypeHintMatch(
        function_name="entity_registry_visible_default",
        return_type="bool",
    ),
    TypeHintMatch(
        function_name="attribution",
        return_type=["str", None],
    ),
    TypeHintMatch(
        function_name="entity_category",
        return_type=["EntityCategory", None],
    ),
    TypeHintMatch(
        function_name="async_removed_from_registry",
        return_type=None,
    ),
    TypeHintMatch(
        function_name="async_added_to_hass",
        return_type=None,
    ),
    TypeHintMatch(
        function_name="async_will_remove_from_hass",
        return_type=None,
    ),
    TypeHintMatch(
        function_name="async_registry_entry_updated",
        return_type=None,
    ),
    TypeHintMatch(
        function_name="update",
        return_type=None,
        has_async_counterpart=True,
    ),
]
_TOGGLE_ENTITY_MATCH: list[TypeHintMatch] = [
    TypeHintMatch(
        function_name="is_on",
        return_type=["bool", None],
    ),
    TypeHintMatch(
        function_name="turn_on",
        kwargs_type="Any",
        return_type=None,
        has_async_counterpart=True,
    ),
    TypeHintMatch(
        function_name="turn_off",
        kwargs_type="Any",
        return_type=None,
        has_async_counterpart=True,
    ),
    TypeHintMatch(
        function_name="toggle",
        kwargs_type="Any",
        return_type=None,
        has_async_counterpart=True,
    ),
]
_INHERITANCE_MATCH: dict[str, list[ClassTypeHintMatch]] = {
    # "air_quality": [],  # ignored as deprecated
    "alarm_control_panel": [
        ClassTypeHintMatch(
            base_class="Entity",
            matches=_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="AlarmControlPanelEntity",
            matches=[
                TypeHintMatch(
                    function_name="device_class",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="code_format",
                    return_type=["CodeFormat", None],
                ),
                TypeHintMatch(
                    function_name="changed_by",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="code_arm_required",
                    return_type="bool",
                ),
                TypeHintMatch(
                    function_name="supported_features",
                    return_type="int",
                ),
                TypeHintMatch(
                    function_name="alarm_disarm",
                    named_arg_types={
                        "code": "str | None",
                    },
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="alarm_arm_home",
                    named_arg_types={
                        "code": "str | None",
                    },
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="alarm_arm_away",
                    named_arg_types={
                        "code": "str | None",
                    },
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="alarm_arm_night",
                    named_arg_types={
                        "code": "str | None",
                    },
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="alarm_arm_vacation",
                    named_arg_types={
                        "code": "str | None",
                    },
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="alarm_trigger",
                    named_arg_types={
                        "code": "str | None",
                    },
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="alarm_arm_custom_bypass",
                    named_arg_types={
                        "code": "str | None",
                    },
                    return_type=None,
                    has_async_counterpart=True,
                ),
            ],
        ),
    ],
    "binary_sensor": [
        ClassTypeHintMatch(
            base_class="Entity",
            matches=_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="BinarySensorEntity",
            matches=[
                TypeHintMatch(
                    function_name="device_class",
                    return_type=["BinarySensorDeviceClass", "str", None],
                ),
                TypeHintMatch(
                    function_name="is_on",
                    return_type=["bool", None],
                ),
            ],
        ),
    ],
    "button": [
        ClassTypeHintMatch(
            base_class="Entity",
            matches=_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="ButtonEntity",
            matches=[
                TypeHintMatch(
                    function_name="device_class",
                    return_type=["ButtonDeviceClass", "str", None],
                ),
                TypeHintMatch(
                    function_name="press",
                    return_type=None,
                    has_async_counterpart=True,
                ),
            ],
        ),
    ],
    "calendar": [
        ClassTypeHintMatch(
            base_class="Entity",
            matches=_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="CalendarEntity",
            matches=[
                TypeHintMatch(
                    function_name="event",
                    return_type=["CalendarEvent", None],
                ),
                TypeHintMatch(
                    function_name="async_get_events",
                    arg_types={
                        1: "HomeAssistant",
                        2: "datetime",
                        3: "datetime",
                    },
                    return_type="list[CalendarEvent]",
                ),
            ],
        ),
    ],
    "camera": [
        ClassTypeHintMatch(
            base_class="Entity",
            matches=_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="Camera",
            matches=[
                TypeHintMatch(
                    function_name="entity_picture",
                    return_type="str",
                ),
                TypeHintMatch(
                    function_name="supported_features",
                    return_type="int",
                ),
                TypeHintMatch(
                    function_name="is_recording",
                    return_type="bool",
                ),
                TypeHintMatch(
                    function_name="is_streaming",
                    return_type="bool",
                ),
                TypeHintMatch(
                    function_name="brand",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="motion_detection_enabled",
                    return_type="bool",
                ),
                TypeHintMatch(
                    function_name="model",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="frame_interval",
                    return_type="float",
                ),
                TypeHintMatch(
                    function_name="frontend_stream_type",
                    return_type=["StreamType", None],
                ),
                TypeHintMatch(
                    function_name="available",
                    return_type="bool",
                ),
                TypeHintMatch(
                    function_name="async_create_stream",
                    return_type=["Stream", None],
                ),
                TypeHintMatch(
                    function_name="stream_source",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="async_handle_web_rtc_offer",
                    arg_types={
                        1: "str",
                    },
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="camera_image",
                    named_arg_types={
                        "width": "int | None",
                        "height": "int | None",
                    },
                    return_type=["bytes", None],
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="handle_async_still_stream",
                    arg_types={
                        1: "Request",
                        2: "float",
                    },
                    return_type="StreamResponse",
                ),
                TypeHintMatch(
                    function_name="handle_async_mjpeg_stream",
                    arg_types={
                        1: "Request",
                    },
                    return_type=["StreamResponse", None],
                ),
                TypeHintMatch(
                    function_name="is_on",
                    return_type="bool",
                ),
                TypeHintMatch(
                    function_name="turn_off",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="turn_on",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="enable_motion_detection",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="disable_motion_detection",
                    return_type=None,
                    has_async_counterpart=True,
                ),
            ],
        ),
    ],
    "climate": [
        ClassTypeHintMatch(
            base_class="Entity",
            matches=_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="ClimateEntity",
            matches=[
                TypeHintMatch(
                    function_name="precision",
                    return_type="float",
                ),
                TypeHintMatch(
                    function_name="temperature_unit",
                    return_type="str",
                ),
                TypeHintMatch(
                    function_name="current_humidity",
                    return_type=["int", None],
                ),
                TypeHintMatch(
                    function_name="target_humidity",
                    return_type=["int", None],
                ),
                TypeHintMatch(
                    function_name="hvac_mode",
                    return_type=["HVACMode", "str", None],
                ),
                TypeHintMatch(
                    function_name="hvac_modes",
                    return_type=["list[HVACMode]", "list[str]"],
                ),
                TypeHintMatch(
                    function_name="hvac_action",
                    return_type=["HVACAction", "str", None],
                ),
                TypeHintMatch(
                    function_name="current_temperature",
                    return_type=["float", None],
                ),
                TypeHintMatch(
                    function_name="target_temperature",
                    return_type=["float", None],
                ),
                TypeHintMatch(
                    function_name="target_temperature_step",
                    return_type=["float", None],
                ),
                TypeHintMatch(
                    function_name="target_temperature_high",
                    return_type=["float", None],
                ),
                TypeHintMatch(
                    function_name="target_temperature_low",
                    return_type=["float", None],
                ),
                TypeHintMatch(
                    function_name="preset_mode",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="preset_modes",
                    return_type=["list[str]", None],
                ),
                TypeHintMatch(
                    function_name="is_aux_heat",
                    return_type=["bool", None],
                ),
                TypeHintMatch(
                    function_name="fan_mode",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="fan_modes",
                    return_type=["list[str]", None],
                ),
                TypeHintMatch(
                    function_name="swing_mode",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="swing_modes",
                    return_type=["list[str]", None],
                ),
                TypeHintMatch(
                    function_name="set_temperature",
                    kwargs_type="Any",
                    return_type="None",
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="set_humidity",
                    arg_types={
                        1: "int",
                    },
                    return_type="None",
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="set_fan_mode",
                    arg_types={
                        1: "str",
                    },
                    return_type="None",
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="set_hvac_mode",
                    arg_types={
                        1: "HVACMode",
                    },
                    return_type="None",
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="set_swing_mode",
                    arg_types={
                        1: "str",
                    },
                    return_type="None",
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="set_preset_mode",
                    arg_types={
                        1: "str",
                    },
                    return_type="None",
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="turn_aux_heat_on",
                    return_type="None",
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="turn_aux_heat_off",
                    return_type="None",
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="turn_on",
                    return_type="None",
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="turn_off",
                    return_type="None",
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="supported_features",
                    return_type="int",
                ),
                TypeHintMatch(
                    function_name="min_temp",
                    return_type="float",
                ),
                TypeHintMatch(
                    function_name="max_temp",
                    return_type="float",
                ),
                TypeHintMatch(
                    function_name="min_humidity",
                    return_type="int",
                ),
                TypeHintMatch(
                    function_name="max_humidity",
                    return_type="int",
                ),
            ],
        ),
    ],
    "cover": [
        ClassTypeHintMatch(
            base_class="Entity",
            matches=_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="CoverEntity",
            matches=[
                TypeHintMatch(
                    function_name="device_class",
                    return_type=["CoverDeviceClass", "str", None],
                ),
                TypeHintMatch(
                    function_name="current_cover_position",
                    return_type=["int", None],
                ),
                TypeHintMatch(
                    function_name="current_cover_tilt_position",
                    return_type=["int", None],
                ),
                TypeHintMatch(
                    function_name="is_opening",
                    return_type=["bool", None],
                ),
                TypeHintMatch(
                    function_name="is_closing",
                    return_type=["bool", None],
                ),
                TypeHintMatch(
                    function_name="is_closed",
                    return_type=["bool", None],
                ),
                TypeHintMatch(
                    function_name="open_cover",
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="close_cover",
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="toggle",
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="set_cover_position",
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="stop_cover",
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="open_cover_tilt",
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="close_cover_tilt",
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="set_cover_tilt_position",
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="stop_cover_tilt",
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="toggle_tilt",
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                ),
            ],
        ),
    ],
    "fan": [
        ClassTypeHintMatch(
            base_class="Entity",
            matches=_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="ToggleEntity",
            matches=_TOGGLE_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="FanEntity",
            matches=[
                TypeHintMatch(
                    function_name="device_class",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="percentage",
                    return_type=["int", None],
                ),
                TypeHintMatch(
                    function_name="speed_count",
                    return_type="int",
                ),
                TypeHintMatch(
                    function_name="percentage_step",
                    return_type="float",
                ),
                TypeHintMatch(
                    function_name="current_direction",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="oscillating",
                    return_type=["bool", None],
                ),
                TypeHintMatch(
                    function_name="preset_mode",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="preset_modes",
                    return_type=["list[str]", None],
                ),
                TypeHintMatch(
                    function_name="set_percentage",
                    arg_types={1: "int"},
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="set_preset_mode",
                    arg_types={1: "str"},
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="set_direction",
                    arg_types={1: "str"},
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="turn_on",
                    named_arg_types={
                        "percentage": "int | None",
                        "preset_mode": "str | None",
                    },
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="oscillate",
                    arg_types={1: "bool"},
                    return_type=None,
                    has_async_counterpart=True,
                ),
            ],
        ),
    ],
    "geo_location": [
        ClassTypeHintMatch(
            base_class="Entity",
            matches=_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="GeolocationEvent",
            matches=[
                TypeHintMatch(
                    function_name="source",
                    return_type="str",
                ),
                TypeHintMatch(
                    function_name="distance",
                    return_type=["float", None],
                ),
                TypeHintMatch(
                    function_name="latitude",
                    return_type=["float", None],
                ),
                TypeHintMatch(
                    function_name="longitude",
                    return_type=["float", None],
                ),
            ],
        ),
    ],
    "light": [
        ClassTypeHintMatch(
            base_class="Entity",
            matches=_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="ToggleEntity",
            matches=_TOGGLE_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="LightEntity",
            matches=[
                TypeHintMatch(
                    function_name="brightness",
                    return_type=["int", None],
                ),
                TypeHintMatch(
                    function_name="color_mode",
                    return_type=["ColorMode", "str", None],
                ),
                TypeHintMatch(
                    function_name="hs_color",
                    return_type=["tuple[float, float]", None],
                ),
                TypeHintMatch(
                    function_name="xy_color",
                    return_type=["tuple[float, float]", None],
                ),
                TypeHintMatch(
                    function_name="rgb_color",
                    return_type=["tuple[int, int, int]", None],
                ),
                TypeHintMatch(
                    function_name="rgbw_color",
                    return_type=["tuple[int, int, int, int]", None],
                ),
                TypeHintMatch(
                    function_name="rgbww_color",
                    return_type=["tuple[int, int, int, int, int]", None],
                ),
                TypeHintMatch(
                    function_name="color_temp",
                    return_type=["int", None],
                ),
                TypeHintMatch(
                    function_name="min_mireds",
                    return_type="int",
                ),
                TypeHintMatch(
                    function_name="max_mireds",
                    return_type="int",
                ),
                TypeHintMatch(
                    function_name="white_value",
                    return_type=["int", None],
                ),
                TypeHintMatch(
                    function_name="effect_list",
                    return_type=["list[str]", None],
                ),
                TypeHintMatch(
                    function_name="effect",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="capability_attributes",
                    return_type=["dict[str, Any]", None],
                ),
                TypeHintMatch(
                    function_name="supported_color_modes",
                    return_type=["set[ColorMode]", "set[str]", None],
                ),
                TypeHintMatch(
                    function_name="supported_features",
                    return_type="int",
                ),
                TypeHintMatch(
                    function_name="turn_on",
                    named_arg_types={
                        "brightness": "int | None",
                        "brightness_pct": "float | None",
                        "brightness_step": "int | None",
                        "brightness_step_pct": "float | None",
                        "color_name": "str | None",
                        "color_temp": "int | None",
                        "effect": "str | None",
                        "flash": "str | None",
                        "kelvin": "int | None",
                        "hs_color": "tuple[float, float] | None",
                        "rgb_color": "tuple[int, int, int] | None",
                        "rgbw_color": "tuple[int, int, int, int] | None",
                        "rgbww_color": "tuple[int, int, int, int, int] | None",
                        "transition": "float | None",
                        "xy_color": "tuple[float, float] | None",
                        "white": "int | None",
                        "white_value": "int | None",
                    },
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                ),
            ],
        ),
    ],
    "lock": [
        ClassTypeHintMatch(
            base_class="Entity",
            matches=_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="LockEntity",
            matches=[
                TypeHintMatch(
                    function_name="device_class",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="changed_by",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="code_format",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="is_locked",
                    return_type=["bool", None],
                ),
                TypeHintMatch(
                    function_name="is_locking",
                    return_type=["bool", None],
                ),
                TypeHintMatch(
                    function_name="is_unlocking",
                    return_type=["bool", None],
                ),
                TypeHintMatch(
                    function_name="is_jammed",
                    return_type=["bool", None],
                ),
                TypeHintMatch(
                    function_name="lock",
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="unlock",
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="open",
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                ),
            ],
        ),
    ],
}


def _is_valid_type(
    expected_type: list[str] | str | None | object,
    node: nodes.NodeNG,
    in_return: bool = False,
) -> bool:
    """Check the argument node against the expected type."""
    if expected_type is UNDEFINED:
        return True

    # Special case for device_class
    if expected_type == DEVICE_CLASS and in_return:
        return (
            isinstance(node, nodes.Name)
            and node.name.endswith("DeviceClass")
            or isinstance(node, nodes.Attribute)
            and node.attrname.endswith("DeviceClass")
        )

    if isinstance(expected_type, list):
        for expected_type_item in expected_type:
            if _is_valid_type(expected_type_item, node, in_return):
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
        # Handle special case of Mapping[xxx, Any]
        if in_return and match.group(1) == "Mapping" and match.group(3) == "Any":
            return (
                isinstance(node, nodes.Subscript)
                and isinstance(node.value, nodes.Name)
                # We accept dict when Mapping is needed
                and node.value.name in ("Mapping", "dict")
                and isinstance(node.slice, nodes.Tuple)
                and _is_valid_type(match.group(2), node.slice.elts[0])
                # Ignore second item
                # and _is_valid_type(match.group(3), node.slice.elts[1])
            )
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
    if _is_valid_type(match.return_type, node, True):
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


def _get_named_annotation(
    node: nodes.FunctionDef, key: str
) -> tuple[nodes.NodeNG, nodes.NodeNG] | tuple[None, None]:
    args = node.args
    for index, arg_node in enumerate(args.args):
        if key == arg_node.name:
            return arg_node, args.annotations[index]

    for index, arg_node in enumerate(args.kwonlyargs):
        if key == arg_node.name:
            return arg_node, args.kwonlyargs_annotations[index]

    return None, None


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
            "Argument %s should be of type %s",
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
                "default": False,
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
            self._class_matchers.extend(class_matches)

        if not self.linter.config.ignore_missing_annotations and (
            property_matches := _INHERITANCE_MATCH.get(module_platform)
        ):
            self._class_matchers.extend(property_matches)

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
                if match.need_to_check_function(function_node):
                    self._check_function(function_node, match)

    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        """Called when a FunctionDef node is visited."""
        for match in self._function_matchers:
            if not match.need_to_check_function(node) or node.is_method():
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

        # Check that all positional arguments are correctly annotated.
        if match.arg_types:
            for key, expected_type in match.arg_types.items():
                if not _is_valid_type(expected_type, annotations[key]):
                    self.add_message(
                        "hass-argument-type",
                        node=node.args.args[key],
                        args=(key + 1, expected_type),
                    )

        # Check that all keyword arguments are correctly annotated.
        if match.named_arg_types is not None:
            for arg_name, expected_type in match.named_arg_types.items():
                arg_node, annotation = _get_named_annotation(node, arg_name)
                if arg_node and not _is_valid_type(expected_type, annotation):
                    self.add_message(
                        "hass-argument-type",
                        node=arg_node,
                        args=(arg_name, expected_type),
                    )

        # Check that kwargs is correctly annotated.
        if match.kwargs_type and not _is_valid_type(
            match.kwargs_type, node.args.kwargannotation
        ):
            self.add_message(
                "hass-argument-type",
                node=node,
                args=(node.args.kwarg, match.kwargs_type),
            )

        # Check the return type.
        if not _is_valid_return_type(match, node.returns):
            self.add_message(
                "hass-return-type", node=node, args=match.return_type or "None"
            )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassTypeHintChecker(linter))
