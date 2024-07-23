"""Plugin to enforce type hints on specific functions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import TYPE_CHECKING

from astroid import nodes
from astroid.exceptions import NameInferenceError
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from homeassistant.const import Platform

if TYPE_CHECKING:
    # InferenceResult is available only from astroid >= 2.12.0
    # pre-commit should still work on out of date environments
    from astroid.typing import InferenceResult

_COMMON_ARGUMENTS: dict[str, list[str]] = {
    "hass": ["HomeAssistant", "HomeAssistant | None"]
}
_PLATFORMS: set[str] = {platform.value for platform in Platform}
_KNOWN_GENERIC_TYPES: set[str] = {
    "ConfigEntry",
}
_KNOWN_GENERIC_TYPES_TUPLE = tuple(_KNOWN_GENERIC_TYPES)


class _Special(Enum):
    """Sentinel values."""

    UNDEFINED = 1


@dataclass
class TypeHintMatch:
    """Class for pattern matching."""

    function_name: str
    return_type: list[str | _Special | None] | str | _Special | None
    arg_types: dict[int, str] | None = None
    """arg_types is for positional arguments"""
    named_arg_types: dict[str, str] | None = None
    """named_arg_types is for named or keyword arguments"""
    kwargs_type: str | None = None
    """kwargs_type is for the special case `**kwargs`"""
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


@dataclass(kw_only=True)
class ClassTypeHintMatch:
    """Class for pattern matching."""

    base_class: str
    exclude_base_classes: set[str] | None = None
    matches: list[TypeHintMatch]


_INNER_MATCH = r"((?:[\w\| ]+)|(?:\.{3})|(?:\w+\[.+\]))"
_TYPE_HINT_MATCHERS: dict[str, re.Pattern[str]] = {
    # a_or_b matches items such as "DiscoveryInfoType | None"
    # or "dict | list | None"
    "a_or_b": re.compile(rf"^(.+) \| {_INNER_MATCH}$"),
}
_INNER_MATCH_POSSIBILITIES = [i + 1 for i in range(5)]
_TYPE_HINT_MATCHERS.update(
    {
        f"x_of_y_{i}": re.compile(
            rf"^(\w+)\[{_INNER_MATCH}" + f", {_INNER_MATCH}" * (i - 1) + r"\]$"
        )
        for i in _INNER_MATCH_POSSIBILITIES
    }
)


_MODULE_REGEX: re.Pattern[str] = re.compile(r"^homeassistant\.components\.\w+(\.\w+)?$")

_METHOD_MATCH: list[TypeHintMatch] = [
    TypeHintMatch(
        function_name="__init__",
        return_type=None,
    ),
]

_TEST_FIXTURES: dict[str, list[str] | str] = {
    "aioclient_mock": "AiohttpClientMocker",
    "aiohttp_client": "ClientSessionGenerator",
    "area_registry": "AreaRegistry",
    "async_setup_recorder_instance": "RecorderInstanceGenerator",
    "caplog": "pytest.LogCaptureFixture",
    "current_request_with_host": "None",
    "device_registry": "DeviceRegistry",
    "enable_bluetooth": "None",
    "enable_custom_integrations": "None",
    "enable_nightly_purge": "bool",
    "enable_statistics": "bool",
    "enable_schema_validation": "bool",
    "entity_registry": "EntityRegistry",
    "entity_registry_enabled_by_default": "None",
    "freezer": "FrozenDateTimeFactory",
    "hass_access_token": "str",
    "hass_admin_credential": "Credentials",
    "hass_admin_user": "MockUser",
    "hass_client": "ClientSessionGenerator",
    "hass_client_no_auth": "ClientSessionGenerator",
    "hass_config": "ConfigType",
    "hass_config_yaml": "str",
    "hass_config_yaml_files": "dict[str, str]",
    "hass_owner_user": "MockUser",
    "hass_read_only_access_token": "str",
    "hass_read_only_user": "MockUser",
    "hass_recorder": "Callable[..., HomeAssistant]",
    "hass_storage": "dict[str, Any]",
    "hass_supervisor_access_token": "str",
    "hass_supervisor_user": "MockUser",
    "hass_ws_client": "WebSocketGenerator",
    "issue_registry": "IssueRegistry",
    "legacy_auth": "LegacyApiPasswordAuthProvider",
    "local_auth": "HassAuthProvider",
    "mock_async_zeroconf": "None",
    "mock_bleak_scanner_start": "MagicMock",
    "mock_bluetooth": "None",
    "mock_bluetooth_adapters": "None",
    "mock_device_tracker_conf": "list[Device]",
    "mock_get_source_ip": "None",
    "mock_hass_config": "None",
    "mock_hass_config_yaml": "None",
    "mock_zeroconf": "None",
    "mqtt_client_mock": "MqttMockPahoClient",
    "mqtt_mock": "MqttMockHAClient",
    "mqtt_mock_entry": "MqttMockHAClientGenerator",
    "recorder_db_url": "str",
    "recorder_mock": "Recorder",
    "requests_mock": "requests_mock.Mocker",
    "snapshot": "SnapshotAssertion",
    "stub_blueprint_populate": "None",
    "tmp_path": "Path",
    "tmpdir": "py.path.local",
}
_TEST_FUNCTION_MATCH = TypeHintMatch(
    function_name="test_*",
    return_type=None,
)


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
        TypeHintMatch(
            function_name="async_reset_platform",
            arg_types={
                0: "HomeAssistant",
                1: "str",
            },
            return_type=None,
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
                1: "MediaType | str",
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
                3: "MediaType | str",
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
                2: "SeeCallback",
                3: "DiscoveryInfoType | None",
            },
            return_type="bool",
        ),
        TypeHintMatch(
            function_name="async_setup_scanner",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigType",
                2: "AsyncSeeCallback",
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
            return_type=["DeviceScanner", None],
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
                2: "TriggerActionType",
                3: "TriggerInfo",
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
            return_type="Mapping[str, Any]",
        ),
        TypeHintMatch(
            function_name="async_get_device_diagnostics",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigEntry",
                2: "DeviceEntry",
            },
            return_type="Mapping[str, Any]",
        ),
    ],
    "notify": [
        TypeHintMatch(
            function_name="get_service",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigType",
                2: "DiscoveryInfoType | None",
            },
            return_type=["BaseNotificationService", None],
            has_async_counterpart=True,
        ),
    ],
}

_CLASS_MATCH: dict[str, list[ClassTypeHintMatch]] = {
    "config_flow": [
        ClassTypeHintMatch(
            base_class="FlowHandler",
            exclude_base_classes={"ConfigEntryBaseFlow"},
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
                ),
                TypeHintMatch(
                    function_name="async_step_dhcp",
                    arg_types={
                        1: "DhcpServiceInfo",
                    },
                    return_type="ConfigFlowResult",
                ),
                TypeHintMatch(
                    function_name="async_step_hassio",
                    arg_types={
                        1: "HassioServiceInfo",
                    },
                    return_type="ConfigFlowResult",
                ),
                TypeHintMatch(
                    function_name="async_step_homekit",
                    arg_types={
                        1: "ZeroconfServiceInfo",
                    },
                    return_type="ConfigFlowResult",
                ),
                TypeHintMatch(
                    function_name="async_step_mqtt",
                    arg_types={
                        1: "MqttServiceInfo",
                    },
                    return_type="ConfigFlowResult",
                ),
                TypeHintMatch(
                    function_name="async_step_reauth",
                    arg_types={
                        1: "Mapping[str, Any]",
                    },
                    return_type="ConfigFlowResult",
                ),
                TypeHintMatch(
                    function_name="async_step_ssdp",
                    arg_types={
                        1: "SsdpServiceInfo",
                    },
                    return_type="ConfigFlowResult",
                ),
                TypeHintMatch(
                    function_name="async_step_usb",
                    arg_types={
                        1: "UsbServiceInfo",
                    },
                    return_type="ConfigFlowResult",
                ),
                TypeHintMatch(
                    function_name="async_step_zeroconf",
                    arg_types={
                        1: "ZeroconfServiceInfo",
                    },
                    return_type="ConfigFlowResult",
                ),
                TypeHintMatch(
                    function_name="async_step_*",
                    arg_types={},
                    return_type="ConfigFlowResult",
                ),
            ],
        ),
        ClassTypeHintMatch(
            base_class="OptionsFlow",
            matches=[
                TypeHintMatch(
                    function_name="async_step_*",
                    arg_types={},
                    return_type="ConfigFlowResult",
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
        return_type=["str", "UndefinedType", None],
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
        function_name="extra_state_attributes",
        return_type=["Mapping[str, Any]", None],
    ),
    TypeHintMatch(
        function_name="device_info",
        return_type=["DeviceInfo", None],
    ),
    TypeHintMatch(
        function_name="device_class",
        return_type=["str", None],
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
_RESTORE_ENTITY_MATCH: list[TypeHintMatch] = [
    TypeHintMatch(
        function_name="async_get_last_state",
        return_type=["State", None],
    ),
    TypeHintMatch(
        function_name="async_get_last_extra_data",
        return_type=["ExtraStoredData", None],
    ),
    TypeHintMatch(
        function_name="extra_restore_state_data",
        return_type=["ExtraStoredData", None],
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
            base_class="RestoreEntity",
            matches=_RESTORE_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="AlarmControlPanelEntity",
            matches=[
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
                    return_type="AlarmControlPanelEntityFeature",
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
            base_class="RestoreEntity",
            matches=_RESTORE_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="BinarySensorEntity",
            matches=[
                TypeHintMatch(
                    function_name="device_class",
                    return_type=["BinarySensorDeviceClass", None],
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
            base_class="RestoreEntity",
            matches=_RESTORE_ENTITY_MATCH,
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
            base_class="RestoreEntity",
            matches=_RESTORE_ENTITY_MATCH,
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
            base_class="RestoreEntity",
            matches=_RESTORE_ENTITY_MATCH,
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
                    return_type="CameraEntityFeature",
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
            base_class="RestoreEntity",
            matches=_RESTORE_ENTITY_MATCH,
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
                    return_type=["float", None],
                ),
                TypeHintMatch(
                    function_name="target_humidity",
                    return_type=["float", None],
                ),
                TypeHintMatch(
                    function_name="hvac_mode",
                    return_type=["HVACMode", None],
                ),
                TypeHintMatch(
                    function_name="hvac_modes",
                    return_type="list[HVACMode]",
                ),
                TypeHintMatch(
                    function_name="hvac_action",
                    return_type=["HVACAction", None],
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
                    return_type="ClimateEntityFeature",
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
                    return_type="float",
                ),
                TypeHintMatch(
                    function_name="max_humidity",
                    return_type="float",
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
            base_class="RestoreEntity",
            matches=_RESTORE_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="CoverEntity",
            matches=[
                TypeHintMatch(
                    function_name="device_class",
                    return_type=["CoverDeviceClass", None],
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
                    function_name="supported_features",
                    return_type="CoverEntityFeature",
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
    "device_tracker": [
        ClassTypeHintMatch(
            base_class="Entity",
            matches=_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="RestoreEntity",
            matches=_RESTORE_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="BaseTrackerEntity",
            matches=[
                TypeHintMatch(
                    function_name="battery_level",
                    return_type=["int", None],
                ),
                TypeHintMatch(
                    function_name="source_type",
                    return_type=["SourceType", "str"],
                ),
            ],
        ),
        ClassTypeHintMatch(
            base_class="TrackerEntity",
            matches=[
                TypeHintMatch(
                    function_name="force_update",
                    return_type="bool",
                ),
                TypeHintMatch(
                    function_name="location_accuracy",
                    return_type="int",
                ),
                TypeHintMatch(
                    function_name="location_name",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="latitude",
                    return_type=["float", None],
                ),
                TypeHintMatch(
                    function_name="longitude",
                    return_type=["float", None],
                ),
                TypeHintMatch(
                    function_name="state",
                    return_type=["str", None],
                ),
            ],
        ),
        ClassTypeHintMatch(
            base_class="ScannerEntity",
            matches=[
                TypeHintMatch(
                    function_name="ip_address",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="mac_address",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="hostname",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="state",
                    return_type="str",
                ),
                TypeHintMatch(
                    function_name="is_connected",
                    return_type="bool",
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
            base_class="RestoreEntity",
            matches=_RESTORE_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="ToggleEntity",
            matches=_TOGGLE_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="FanEntity",
            matches=[
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
                    function_name="supported_features",
                    return_type="FanEntityFeature",
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
            base_class="RestoreEntity",
            matches=_RESTORE_ENTITY_MATCH,
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
    "image_processing": [
        ClassTypeHintMatch(
            base_class="Entity",
            matches=_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="RestoreEntity",
            matches=_RESTORE_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="ImageProcessingEntity",
            matches=[
                TypeHintMatch(
                    function_name="camera_entity",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="confidence",
                    return_type=["float", None],
                ),
                TypeHintMatch(
                    function_name="device_class",
                    return_type=["ImageProcessingDeviceClass", None],
                ),
                TypeHintMatch(
                    function_name="process_image",
                    arg_types={1: "bytes"},
                    return_type=None,
                    has_async_counterpart=True,
                ),
            ],
        ),
        ClassTypeHintMatch(
            base_class="ImageProcessingFaceEntity",
            matches=[
                TypeHintMatch(
                    function_name="process_faces",
                    arg_types={
                        1: "list[FaceInformation]",
                        2: "int",
                    },
                    return_type=None,
                    has_async_counterpart=True,
                ),
            ],
        ),
    ],
    "humidifier": [
        ClassTypeHintMatch(
            base_class="Entity",
            matches=_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="RestoreEntity",
            matches=_RESTORE_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="ToggleEntity",
            matches=_TOGGLE_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="HumidifierEntity",
            matches=[
                TypeHintMatch(
                    function_name="available_modes",
                    return_type=["list[str]", None],
                ),
                TypeHintMatch(
                    function_name="device_class",
                    return_type=["HumidifierDeviceClass", None],
                ),
                TypeHintMatch(
                    function_name="min_humidity",
                    return_type=["float"],
                ),
                TypeHintMatch(
                    function_name="max_humidity",
                    return_type=["float"],
                ),
                TypeHintMatch(
                    function_name="mode",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="supported_features",
                    return_type="HumidifierEntityFeature",
                ),
                TypeHintMatch(
                    function_name="target_humidity",
                    return_type=["float", None],
                ),
                TypeHintMatch(
                    function_name="set_humidity",
                    arg_types={1: "int"},
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="set_mode",
                    arg_types={1: "str"},
                    return_type=None,
                    has_async_counterpart=True,
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
            base_class="RestoreEntity",
            matches=_RESTORE_ENTITY_MATCH,
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
                    return_type="LightEntityFeature",
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
            base_class="RestoreEntity",
            matches=_RESTORE_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="LockEntity",
            matches=[
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
                    function_name="supported_features",
                    return_type="LockEntityFeature",
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
    "mailbox": [
        ClassTypeHintMatch(
            base_class="Mailbox",
            matches=[
                TypeHintMatch(
                    function_name="media_type",
                    return_type="str",
                ),
                TypeHintMatch(
                    function_name="can_delete",
                    return_type="bool",
                ),
                TypeHintMatch(
                    function_name="has_media",
                    return_type="bool",
                ),
                TypeHintMatch(
                    function_name="async_get_media",
                    arg_types={1: "str"},
                    return_type="bytes",
                ),
                TypeHintMatch(
                    function_name="async_get_messages",
                    return_type="list[dict[str, Any]]",
                ),
                TypeHintMatch(
                    function_name="async_delete",
                    arg_types={1: "str"},
                    return_type="bool",
                ),
            ],
        ),
    ],
    "media_player": [
        ClassTypeHintMatch(
            base_class="Entity",
            matches=_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="RestoreEntity",
            matches=_RESTORE_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="MediaPlayerEntity",
            matches=[
                TypeHintMatch(
                    function_name="device_class",
                    return_type=["MediaPlayerDeviceClass", None],
                ),
                TypeHintMatch(
                    function_name="state",
                    return_type=["MediaPlayerState", None],
                ),
                TypeHintMatch(
                    function_name="access_token",
                    return_type="str",
                ),
                TypeHintMatch(
                    function_name="volume_level",
                    return_type=["float", None],
                ),
                TypeHintMatch(
                    function_name="is_volume_muted",
                    return_type=["bool", None],
                ),
                TypeHintMatch(
                    function_name="media_content_id",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="media_content_type",
                    return_type=["MediaType", "str", None],
                ),
                TypeHintMatch(
                    function_name="media_duration",
                    return_type=["int", None],
                ),
                TypeHintMatch(
                    function_name="media_position",
                    return_type=["int", None],
                ),
                TypeHintMatch(
                    function_name="media_position_updated_at",
                    return_type=["datetime", None],
                ),
                TypeHintMatch(
                    function_name="media_image_url",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="media_image_remotely_accessible",
                    return_type="bool",
                ),
                TypeHintMatch(
                    function_name="media_image_hash",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="async_get_media_image",
                    return_type="tuple[bytes | None, str | None]",
                ),
                TypeHintMatch(
                    function_name="async_get_browse_image",
                    arg_types={
                        1: "MediaType | str",
                        2: "str",
                        3: "str | None",
                    },
                    return_type="tuple[bytes | None, str | None]",
                ),
                TypeHintMatch(
                    function_name="media_title",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="media_artist",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="media_album_name",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="media_album_artist",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="media_track",
                    return_type=["int", None],
                ),
                TypeHintMatch(
                    function_name="media_series_title",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="media_season",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="media_episode",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="media_channel",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="media_playlist",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="app_id",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="app_name",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="source",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="source_list",
                    return_type=["list[str]", None],
                ),
                TypeHintMatch(
                    function_name="sound_mode",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="sound_mode_list",
                    return_type=["list[str]", None],
                ),
                TypeHintMatch(
                    function_name="shuffle",
                    return_type=["bool", None],
                ),
                TypeHintMatch(
                    function_name="repeat",
                    return_type=["RepeatMode", None],
                ),
                TypeHintMatch(
                    function_name="group_members",
                    return_type=["list[str]", None],
                ),
                TypeHintMatch(
                    function_name="supported_features",
                    return_type="MediaPlayerEntityFeature",
                ),
                TypeHintMatch(
                    function_name="turn_on",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="turn_off",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="mute_volume",
                    arg_types={
                        1: "bool",
                    },
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="set_volume_level",
                    arg_types={
                        1: "float",
                    },
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="media_play",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="media_pause",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="media_stop",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="media_previous_track",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="media_next_track",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="media_seek",
                    arg_types={
                        1: "float",
                    },
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="play_media",
                    arg_types={
                        1: "MediaType | str",
                        2: "str",
                    },
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="select_source",
                    arg_types={
                        1: "str",
                    },
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="select_sound_mode",
                    arg_types={
                        1: "str",
                    },
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="clear_playlist",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="set_shuffle",
                    arg_types={
                        1: "bool",
                    },
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="set_repeat",
                    arg_types={
                        1: "RepeatMode",
                    },
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="toggle",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="volume_up",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="volume_down",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="media_play_pause",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="media_image_local",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="capability_attributes",
                    return_type="dict[str, Any]",
                ),
                TypeHintMatch(
                    function_name="async_browse_media",
                    arg_types={
                        1: "MediaType | str | None",
                        2: "str | None",
                    },
                    return_type="BrowseMedia",
                ),
                TypeHintMatch(
                    function_name="join_players",
                    arg_types={
                        1: "list[str]",
                    },
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="unjoin_player",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="get_browse_image_url",
                    arg_types={
                        1: "str",
                        2: "str",
                        3: "str | None",
                    },
                    return_type="str",
                ),
            ],
        ),
    ],
    "notify": [
        ClassTypeHintMatch(
            base_class="BaseNotificationService",
            matches=[
                TypeHintMatch(
                    function_name="targets",
                    return_type=["Mapping[str, Any]", None],
                ),
                TypeHintMatch(
                    function_name="send_message",
                    arg_types={1: "str"},
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                ),
            ],
        ),
    ],
    "number": [
        ClassTypeHintMatch(
            base_class="Entity",
            matches=_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="RestoreEntity",
            matches=_RESTORE_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="NumberEntity",
            matches=[
                TypeHintMatch(
                    function_name="device_class",
                    return_type=["NumberDeviceClass", None],
                ),
                TypeHintMatch(
                    function_name="capability_attributes",
                    return_type="dict[str, Any]",
                ),
                TypeHintMatch(
                    function_name="native_min_value",
                    return_type="float",
                ),
                TypeHintMatch(
                    function_name="native_max_value",
                    return_type="float",
                ),
                TypeHintMatch(
                    function_name="native_step",
                    return_type=["float", None],
                ),
                TypeHintMatch(
                    function_name="mode",
                    return_type="NumberMode",
                ),
                TypeHintMatch(
                    function_name="native_unit_of_measurement",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="native_value",
                    return_type=["float", None],
                ),
                TypeHintMatch(
                    function_name="set_native_value",
                    arg_types={1: "float"},
                    return_type=None,
                    has_async_counterpart=True,
                ),
            ],
        ),
        ClassTypeHintMatch(
            base_class="RestoreNumber",
            matches=[
                TypeHintMatch(
                    function_name="extra_restore_state_data",
                    return_type="NumberExtraStoredData",
                ),
                TypeHintMatch(
                    function_name="async_get_last_number_data",
                    return_type=["NumberExtraStoredData", None],
                ),
            ],
        ),
    ],
    "remote": [
        ClassTypeHintMatch(
            base_class="Entity",
            matches=_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="RestoreEntity",
            matches=_RESTORE_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="ToggleEntity",
            matches=_TOGGLE_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="RemoteEntity",
            matches=[
                TypeHintMatch(
                    function_name="activity_list",
                    return_type=["list[str]", None],
                ),
                TypeHintMatch(
                    function_name="current_activity",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="supported_features",
                    return_type="RemoteEntityFeature",
                ),
                TypeHintMatch(
                    function_name="send_command",
                    arg_types={1: "Iterable[str]"},
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="learn_command",
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="delete_command",
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                ),
            ],
        ),
    ],
    "scene": [
        ClassTypeHintMatch(
            base_class="Entity",
            matches=_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="RestoreEntity",
            matches=_RESTORE_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="Scene",
            matches=[
                TypeHintMatch(
                    function_name="activate",
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                ),
            ],
        ),
    ],
    "select": [
        ClassTypeHintMatch(
            base_class="Entity",
            matches=_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="RestoreEntity",
            matches=_RESTORE_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="SelectEntity",
            matches=[
                TypeHintMatch(
                    function_name="capability_attributes",
                    return_type="dict[str, Any]",
                ),
                TypeHintMatch(
                    function_name="options",
                    return_type="list[str]",
                ),
                TypeHintMatch(
                    function_name="current_option",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="select_option",
                    return_type=None,
                ),
                TypeHintMatch(
                    function_name="select_option",
                    arg_types={1: "str"},
                    return_type=None,
                    has_async_counterpart=True,
                ),
            ],
        ),
    ],
    "sensor": [
        ClassTypeHintMatch(
            base_class="Entity",
            matches=_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="RestoreEntity",
            matches=_RESTORE_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="SensorEntity",
            matches=[
                TypeHintMatch(
                    function_name="device_class",
                    return_type=["SensorDeviceClass", None],
                ),
                TypeHintMatch(
                    function_name="state_class",
                    return_type=["SensorStateClass", "str", None],
                ),
                TypeHintMatch(
                    function_name="last_reset",
                    return_type=["datetime", None],
                ),
                TypeHintMatch(
                    function_name="native_value",
                    return_type=[
                        "StateType",
                        "str",
                        "int",
                        "float",
                        None,
                        "date",
                        "datetime",
                        "Decimal",
                    ],
                ),
                TypeHintMatch(
                    function_name="native_unit_of_measurement",
                    return_type=["str", None],
                ),
            ],
        ),
        ClassTypeHintMatch(
            base_class="RestoreSensor",
            matches=[
                TypeHintMatch(
                    function_name="extra_restore_state_data",
                    return_type="SensorExtraStoredData",
                ),
                TypeHintMatch(
                    function_name="async_get_last_sensor_data",
                    return_type=["SensorExtraStoredData", None],
                ),
            ],
        ),
    ],
    "siren": [
        ClassTypeHintMatch(
            base_class="Entity",
            matches=_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="RestoreEntity",
            matches=_RESTORE_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="ToggleEntity",
            matches=_TOGGLE_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="SirenEntity",
            matches=[
                TypeHintMatch(
                    function_name="available_tones",
                    return_type=["dict[int, str]", "list[int | str]", None],
                ),
                TypeHintMatch(
                    function_name="supported_features",
                    return_type="SirenEntityFeature",
                ),
            ],
        ),
    ],
    "stt": [
        ClassTypeHintMatch(
            base_class="Provider",
            matches=[
                TypeHintMatch(
                    function_name="supported_languages",
                    return_type="list[str]",
                ),
                TypeHintMatch(
                    function_name="supported_formats",
                    return_type="list[AudioFormats]",
                ),
                TypeHintMatch(
                    function_name="supported_codecs",
                    return_type="list[AudioCodecs]",
                ),
                TypeHintMatch(
                    function_name="supported_bit_rates",
                    return_type="list[AudioBitRates]",
                ),
                TypeHintMatch(
                    function_name="supported_sample_rates",
                    return_type="list[AudioSampleRates]",
                ),
                TypeHintMatch(
                    function_name="supported_channels",
                    return_type="list[AudioChannels]",
                ),
                TypeHintMatch(
                    function_name="async_process_audio_stream",
                    arg_types={1: "SpeechMetadata", 2: "AsyncIterable[bytes]"},
                    return_type="SpeechResult",
                ),
            ],
        ),
    ],
    "switch": [
        ClassTypeHintMatch(
            base_class="Entity",
            matches=_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="RestoreEntity",
            matches=_RESTORE_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="ToggleEntity",
            matches=_TOGGLE_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="SwitchEntity",
            matches=[
                TypeHintMatch(
                    function_name="device_class",
                    return_type=["SwitchDeviceClass", None],
                ),
            ],
        ),
    ],
    "todo": [
        ClassTypeHintMatch(
            base_class="Entity",
            matches=_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="RestoreEntity",
            matches=_RESTORE_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="TodoListEntity",
            matches=[
                TypeHintMatch(
                    function_name="todo_items",
                    return_type=["list[TodoItem]", None],
                ),
                TypeHintMatch(
                    function_name="async_create_todo_item",
                    arg_types={
                        1: "TodoItem",
                    },
                    return_type="None",
                ),
                TypeHintMatch(
                    function_name="async_update_todo_item",
                    arg_types={
                        1: "TodoItem",
                    },
                    return_type="None",
                ),
                TypeHintMatch(
                    function_name="async_delete_todo_items",
                    arg_types={
                        1: "list[str]",
                    },
                    return_type="None",
                ),
                TypeHintMatch(
                    function_name="async_move_todo_item",
                    arg_types={
                        1: "str",
                        2: "str | None",
                    },
                    return_type="None",
                ),
            ],
        ),
    ],
    "tts": [
        ClassTypeHintMatch(
            base_class="Provider",
            matches=[
                TypeHintMatch(
                    function_name="default_language",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="supported_languages",
                    return_type=["list[str]", None],
                ),
                TypeHintMatch(
                    function_name="supported_options",
                    return_type=["list[str]", None],
                ),
                TypeHintMatch(
                    function_name="default_options",
                    return_type=["Mapping[str, Any]", None],
                ),
                TypeHintMatch(
                    function_name="get_tts_audio",
                    arg_types={1: "str", 2: "str", 3: "dict[str, Any]"},
                    return_type="TtsAudioType",
                    has_async_counterpart=True,
                ),
            ],
        ),
    ],
    "update": [
        ClassTypeHintMatch(
            base_class="Entity",
            matches=_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="RestoreEntity",
            matches=_RESTORE_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="UpdateEntity",
            matches=[
                TypeHintMatch(
                    function_name="auto_update",
                    return_type="bool",
                ),
                TypeHintMatch(
                    function_name="installed_version",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="device_class",
                    return_type=["UpdateDeviceClass", None],
                ),
                TypeHintMatch(
                    function_name="in_progress",
                    return_type=["bool", "int", None],
                ),
                TypeHintMatch(
                    function_name="latest_version",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="release_summary",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="release_url",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="supported_features",
                    return_type="UpdateEntityFeature",
                ),
                TypeHintMatch(
                    function_name="title",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="install",
                    arg_types={1: "str | None", 2: "bool"},
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="release_notes",
                    return_type=["str", None],
                    has_async_counterpart=True,
                ),
            ],
        ),
    ],
    "vacuum": [
        ClassTypeHintMatch(
            base_class="Entity",
            matches=_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="RestoreEntity",
            matches=_RESTORE_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="ToggleEntity",
            matches=_TOGGLE_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="_BaseVacuum",
            matches=[
                TypeHintMatch(
                    function_name="battery_level",
                    return_type=["int", None],
                ),
                TypeHintMatch(
                    function_name="battery_icon",
                    return_type="str",
                ),
                TypeHintMatch(
                    function_name="fan_speed",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="fan_speed_list",
                    return_type="list[str]",
                ),
                TypeHintMatch(
                    function_name="supported_features",
                    return_type="VacuumEntityFeature",
                ),
                TypeHintMatch(
                    function_name="stop",
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="return_to_base",
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="clean_spot",
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="locate",
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="set_fan_speed",
                    named_arg_types={
                        "fan_speed": "str",
                    },
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="send_command",
                    named_arg_types={
                        "command": "str",
                        "params": "dict[str, Any] | list[Any] | None",
                    },
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                ),
            ],
        ),
        ClassTypeHintMatch(
            base_class="VacuumEntity",
            matches=[
                TypeHintMatch(
                    function_name="status",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="start_pause",
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="async_pause",
                    return_type=None,
                ),
                TypeHintMatch(
                    function_name="async_start",
                    return_type=None,
                ),
            ],
        ),
        ClassTypeHintMatch(
            base_class="StateVacuumEntity",
            matches=[
                TypeHintMatch(
                    function_name="state",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="start",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="pause",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="async_turn_on",
                    kwargs_type="Any",
                    return_type=None,
                ),
                TypeHintMatch(
                    function_name="async_turn_off",
                    kwargs_type="Any",
                    return_type=None,
                ),
                TypeHintMatch(
                    function_name="async_toggle",
                    kwargs_type="Any",
                    return_type=None,
                ),
            ],
        ),
    ],
    "water_heater": [
        ClassTypeHintMatch(
            base_class="Entity",
            matches=_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="RestoreEntity",
            matches=_RESTORE_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="WaterHeaterEntity",
            matches=[
                TypeHintMatch(
                    function_name="current_operation",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="current_temperature",
                    return_type=["float", None],
                ),
                TypeHintMatch(
                    function_name="is_away_mode_on",
                    return_type=["bool", None],
                ),
                TypeHintMatch(
                    function_name="max_temp",
                    return_type="float",
                ),
                TypeHintMatch(
                    function_name="min_temp",
                    return_type="float",
                ),
                TypeHintMatch(
                    function_name="operation_list",
                    return_type=["list[str]", None],
                ),
                TypeHintMatch(
                    function_name="precision",
                    return_type="float",
                ),
                TypeHintMatch(
                    function_name="supported_features",
                    return_type="WaterHeaterEntityFeature",
                ),
                TypeHintMatch(
                    function_name="target_temperature",
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
                    function_name="temperature_unit",
                    return_type="str",
                ),
                TypeHintMatch(
                    function_name="set_temperature",
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="set_operation_mode",
                    arg_types={1: "str"},
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="turn_away_mode_on",
                    return_type=None,
                    has_async_counterpart=True,
                ),
                TypeHintMatch(
                    function_name="turn_away_mode_off",
                    return_type=None,
                    has_async_counterpart=True,
                ),
            ],
        ),
    ],
    "weather": [
        ClassTypeHintMatch(
            base_class="Entity",
            matches=_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="RestoreEntity",
            matches=_RESTORE_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="WeatherEntity",
            matches=[
                TypeHintMatch(
                    function_name="native_temperature",
                    return_type=["float", None],
                ),
                TypeHintMatch(
                    function_name="native_temperature_unit",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="native_pressure",
                    return_type=["float", None],
                ),
                TypeHintMatch(
                    function_name="native_pressure_unit",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="humidity",
                    return_type=["float", None],
                ),
                TypeHintMatch(
                    function_name="native_wind_speed",
                    return_type=["float", None],
                ),
                TypeHintMatch(
                    function_name="native_wind_speed_unit",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="wind_bearing",
                    return_type=["float", "str", None],
                ),
                TypeHintMatch(
                    function_name="ozone",
                    return_type=["float", None],
                ),
                TypeHintMatch(
                    function_name="native_visibility",
                    return_type=["float", None],
                ),
                TypeHintMatch(
                    function_name="native_visibility_unit",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="forecast",
                    return_type=["list[Forecast]", None],
                ),
                TypeHintMatch(
                    function_name="native_precipitation_unit",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="precision",
                    return_type="float",
                ),
                TypeHintMatch(
                    function_name="condition",
                    return_type=["str", None],
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
    if expected_type is _Special.UNDEFINED:
        return True

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

    # Special case for `xxx[aaa, bbb, ccc, ...]
    if (
        isinstance(node, nodes.Subscript)
        and isinstance(node.slice, nodes.Tuple)
        and (
            match := _TYPE_HINT_MATCHERS[f"x_of_y_{len(node.slice.elts)}"].match(
                expected_type
            )
        )
    ):
        # This special case is separate because we want Mapping[str, Any]
        # to also match dict[str, int] and similar
        if (
            len(node.slice.elts) == 2
            and in_return
            and match.group(1) == "Mapping"
            and match.group(3) == "Any"
        ):
            return (
                isinstance(node.value, nodes.Name)
                # We accept dict when Mapping is needed
                and node.value.name in ("Mapping", "dict")
                and isinstance(node.slice, nodes.Tuple)
                and _is_valid_type(match.group(2), node.slice.elts[0])
                # Ignore second item
                # and _is_valid_type(match.group(3), node.slice.elts[1])
            )

        # This is the default case
        return (
            _is_valid_type(match.group(1), node.value)
            and isinstance(node.slice, nodes.Tuple)
            and all(
                _is_valid_type(match.group(n + 2), node.slice.elts[n], in_return)
                for n in range(len(node.slice.elts))
            )
        )

    # Special case for xxx[yyy]
    if match := _TYPE_HINT_MATCHERS["x_of_y_1"].match(expected_type):
        return (
            isinstance(node, nodes.Subscript)
            and _is_valid_type(match.group(1), node.value)
            and _is_valid_type(match.group(2), node.slice)
        )

    # Special case for float in return type
    if (
        expected_type == "float"
        and in_return
        and isinstance(node, nodes.Name)
        and node.name in ("float", "int")
    ):
        return True

    # Special case for int in argument type
    if (
        expected_type == "int"
        and not in_return
        and isinstance(node, nodes.Name)
        and node.name in ("float", "int")
    ):
        return True

    # Allow subscripts or type aliases for generic types
    if (
        isinstance(node, nodes.Subscript)
        and isinstance(node.value, nodes.Name)
        and node.value.name in _KNOWN_GENERIC_TYPES
        or isinstance(node, nodes.Name)
        and node.name.endswith(_KNOWN_GENERIC_TYPES_TUPLE)
    ):
        return True

    # Name occurs when a namespace is not used, eg. "HomeAssistant"
    if isinstance(node, nodes.Name) and node.name == expected_type:
        return True

    # Attribute occurs when a namespace is used, eg. "core.HomeAssistant"
    return isinstance(node, nodes.Attribute) and (
        node.attrname == expected_type or node.as_string() == expected_type
    )


def _is_valid_return_type(match: TypeHintMatch, node: nodes.NodeNG) -> bool:
    if _is_valid_type(match.return_type, node, True):
        return True

    if isinstance(node, nodes.BinOp):
        return _is_valid_return_type(match, node.left) and _is_valid_return_type(
            match, node.right
        )

    if isinstance(match.return_type, (str, list)) and isinstance(node, nodes.Name):
        if isinstance(match.return_type, str):
            valid_types = {match.return_type}
        else:
            valid_types = {el for el in match.return_type if isinstance(el, str)}
        if "Mapping[str, Any]" in valid_types:
            valid_types.add("TypedDict")

        try:
            for infer_node in node.infer():
                if _check_ancestry(infer_node, valid_types):
                    return True
        except NameInferenceError:
            for class_node in node.root().nodes_of_class(nodes.ClassDef):
                if class_node.name != node.name:
                    continue
                for infer_node in class_node.infer():
                    if _check_ancestry(infer_node, valid_types):
                        return True

    return False


def _check_ancestry(infer_node: InferenceResult, valid_types: set[str]) -> bool:
    if isinstance(infer_node, nodes.ClassDef):
        if infer_node.name in valid_types:
            return True
        for ancestor in infer_node.ancestors():
            if ancestor.name in valid_types:
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
    return any(annotation is not None for annotation in annotations)


def _get_module_platform(module_name: str) -> str | None:
    """Return the platform for the module name."""
    if not (module_match := _MODULE_REGEX.match(module_name)):
        # Ensure `homeassistant.components.<component>`
        # Or `homeassistant.components.<component>.<platform>`
        return None

    platform = module_match.groups()[0]
    return platform.lstrip(".") if platform else "__init__"


def _is_test_function(module_name: str, node: nodes.FunctionDef) -> bool:
    """Return True if function is a pytest function."""
    return module_name.startswith("tests.") and node.name.startswith("test_")


class HassTypeHintChecker(BaseChecker):
    """Checker for setup type hints."""

    name = "hass_enforce_type_hints"
    priority = -1
    msgs = {
        "W7431": (
            "Argument %s should be of type %s in %s",
            "hass-argument-type",
            "Used when method argument type is incorrect",
        ),
        "W7432": (
            "Return type should be %s in %s",
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

    _class_matchers: list[ClassTypeHintMatch]
    _function_matchers: list[TypeHintMatch]
    _module_name: str

    def visit_module(self, node: nodes.Module) -> None:
        """Populate matchers for a Module node."""
        self._class_matchers = []
        self._function_matchers = []
        self._module_name = node.name

        if (module_platform := _get_module_platform(node.name)) is None:
            return

        if module_platform in _PLATFORMS:
            self._function_matchers.extend(_FUNCTION_MATCH["__any_platform__"])

        if function_matches := _FUNCTION_MATCH.get(module_platform):
            self._function_matchers.extend(function_matches)

        if class_matches := _CLASS_MATCH.get(module_platform):
            self._class_matchers.extend(class_matches)

        if property_matches := _INHERITANCE_MATCH.get(module_platform):
            self._class_matchers.extend(property_matches)

        self._class_matchers.reverse()

    def _ignore_function(
        self, node: nodes.FunctionDef, annotations: list[nodes.NodeNG | None]
    ) -> bool:
        """Check if we can skip the function validation."""
        return (
            self.linter.config.ignore_missing_annotations
            and node.returns is None
            and not _has_valid_annotations(annotations)
        )

    def visit_classdef(self, node: nodes.ClassDef) -> None:
        """Apply relevant type hint checks on a ClassDef node."""
        ancestor: nodes.ClassDef
        checked_class_methods: set[str] = set()
        ancestors = list(node.ancestors())  # cache result for inside loop
        for class_matcher in self._class_matchers:
            skip_matcher = False
            if exclude_base_classes := class_matcher.exclude_base_classes:
                for ancestor in ancestors:
                    if ancestor.name in exclude_base_classes:
                        skip_matcher = True
                        break
            if skip_matcher:
                continue
            for ancestor in ancestors:
                if ancestor.name == class_matcher.base_class:
                    self._visit_class_functions(
                        node, class_matcher.matches, checked_class_methods
                    )

    def _visit_class_functions(
        self,
        node: nodes.ClassDef,
        matches: list[TypeHintMatch],
        checked_class_methods: set[str],
    ) -> None:
        cached_methods: list[nodes.FunctionDef] = list(node.mymethods())
        for match in matches:
            for function_node in cached_methods:
                if (
                    function_node.name in checked_class_methods
                    or not match.need_to_check_function(function_node)
                ):
                    continue

                annotations = _get_all_annotations(function_node)
                if self._ignore_function(function_node, annotations):
                    continue

                self._check_function(function_node, match, annotations)
                checked_class_methods.add(function_node.name)

    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        """Apply relevant type hint checks on a FunctionDef node."""
        annotations = _get_all_annotations(node)
        if self._ignore_function(node, annotations):
            return

        # Check that common arguments are correctly typed.
        for arg_name, expected_type in _COMMON_ARGUMENTS.items():
            arg_node, annotation = _get_named_annotation(node, arg_name)
            if arg_node and not _is_valid_type(expected_type, annotation):
                self.add_message(
                    "hass-argument-type",
                    node=arg_node,
                    args=(arg_name, expected_type, node.name),
                )

        # Check method or function matchers.
        if node.is_method():
            matchers = _METHOD_MATCH
        else:
            matchers = self._function_matchers
            if _is_test_function(self._module_name, node):
                self._check_test_function(node, annotations)
        for match in matchers:
            if not match.need_to_check_function(node):
                continue
            self._check_function(node, match, annotations)

    visit_asyncfunctiondef = visit_functiondef

    def _check_function(
        self,
        node: nodes.FunctionDef,
        match: TypeHintMatch,
        annotations: list[nodes.NodeNG | None],
    ) -> None:
        # Check that all positional arguments are correctly annotated.
        if match.arg_types:
            for key, expected_type in match.arg_types.items():
                if (
                    node.args.args[key].name in _COMMON_ARGUMENTS
                    or _is_test_function(self._module_name, node)
                    and node.args.args[key].name in _TEST_FIXTURES
                ):
                    # It has already been checked, avoid double-message
                    continue
                if not _is_valid_type(expected_type, annotations[key]):
                    self.add_message(
                        "hass-argument-type",
                        node=node.args.args[key],
                        args=(key + 1, expected_type, node.name),
                    )

        # Check that all keyword arguments are correctly annotated.
        if match.named_arg_types is not None:
            for arg_name, expected_type in match.named_arg_types.items():
                if (
                    arg_name in _COMMON_ARGUMENTS
                    or _is_test_function(self._module_name, node)
                    and arg_name in _TEST_FIXTURES
                ):
                    # It has already been checked, avoid double-message
                    continue
                arg_node, annotation = _get_named_annotation(node, arg_name)
                if arg_node and not _is_valid_type(expected_type, annotation):
                    self.add_message(
                        "hass-argument-type",
                        node=arg_node,
                        args=(arg_name, expected_type, node.name),
                    )

        # Check that kwargs is correctly annotated.
        if match.kwargs_type and not _is_valid_type(
            match.kwargs_type, node.args.kwargannotation
        ):
            self.add_message(
                "hass-argument-type",
                node=node,
                args=(node.args.kwarg, match.kwargs_type, node.name),
            )

        # Check the return type.
        if not _is_valid_return_type(match, node.returns):
            self.add_message(
                "hass-return-type",
                node=node,
                args=(match.return_type or "None", node.name),
            )

    def _check_test_function(
        self, node: nodes.FunctionDef, annotations: list[nodes.NodeNG | None]
    ) -> None:
        # Check the return type.
        if not _is_valid_return_type(_TEST_FUNCTION_MATCH, node.returns):
            self.add_message(
                "hass-return-type",
                node=node,
                args=(_TEST_FUNCTION_MATCH.return_type or "None", node.name),
            )
        # Check that all positional arguments are correctly annotated.
        for arg_name, expected_type in _TEST_FIXTURES.items():
            arg_node, annotation = _get_named_annotation(node, arg_name)
            if arg_node and not _is_valid_type(expected_type, annotation):
                self.add_message(
                    "hass-argument-type",
                    node=arg_node,
                    args=(arg_name, expected_type, node.name),
                )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassTypeHintChecker(linter))
