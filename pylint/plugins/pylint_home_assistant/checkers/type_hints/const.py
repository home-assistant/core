"""Constants for type hint checking."""

from pylint_home_assistant.const import ANY_PLATFORM, Module, Platform

from .models import ClassTypeHintMatch, TypeHintMatch

_COMMON_ARGUMENTS: dict[str, list[str]] = {
    "hass": ["HomeAssistant", "HomeAssistant | None"]
}

_FORCE_ANNOTATION_PLATFORMS = [Module.CONFIG_FLOW]

_METHOD_MATCH: list[TypeHintMatch] = [
    TypeHintMatch(
        function_name="__init__",
        return_type=None,
    ),
]

_TEST_FIXTURES: dict[str, list[str] | str] = {
    "aioclient_mock": "AiohttpClientMocker",
    "aiohttp_client": "ClientSessionGenerator",
    "aiohttp_server": "Callable[[], TestServer]",
    "area_registry": "AreaRegistry",
    "async_test_recorder": "RecorderInstanceContextManager",
    "async_setup_recorder_instance": "RecorderInstanceGenerator",
    "caplog": "pytest.LogCaptureFixture",
    "capsys": "pytest.CaptureFixture[str]",
    "current_request_with_host": "None",
    "device_registry": "DeviceRegistry",
    "enable_bluetooth": "None",
    "enable_custom_integrations": "None",
    "enable_missing_statistics": "bool",
    "enable_nightly_purge": "bool",
    "enable_statistics": "bool",
    "enable_schema_validation": "bool",
    "entity_registry": "EntityRegistry",
    "entity_registry_enabled_by_default": "None",
    "event_loop": "AbstractEventLoop",
    "freezer": "FrozenDateTimeFactory",
    "hass": "HomeAssistant",
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
    "hass_storage": "dict[str, Any]",
    "hass_supervisor_access_token": "str",
    "hass_supervisor_user": "MockUser",
    "hass_ws_client": "WebSocketGenerator",
    "init_tts_cache_dir_side_effect": "Any",
    "issue_registry": "IssueRegistry",
    "local_auth": "HassAuthProvider",
    "mock_async_zeroconf": "MagicMock",
    "mock_bleak_scanner_start": "MagicMock",
    "mock_bluetooth": "None",
    "mock_bluetooth_adapters": "None",
    "mock_conversation_agent": "MockAgent",
    "mock_device_tracker_conf": "list[Device]",
    "mock_get_source_ip": "_patch",
    "mock_hass_config": "None",
    "mock_hass_config_yaml": "None",
    "mock_tts_cache_dir": "Path",
    "mock_tts_get_cache_files": "MagicMock",
    "mock_tts_init_cache_dir": "MagicMock",
    "mock_zeroconf": "MagicMock",
    "monkeypatch": "pytest.MonkeyPatch",
    "mqtt_client_mock": "MqttMockPahoClient",
    "mqtt_mock": "MqttMockHAClient",
    "mqtt_mock_entry": "MqttMockHAClientGenerator",
    "recorder_db_url": "str",
    "recorder_mock": "Recorder",
    "request": "pytest.FixtureRequest",
    "requests_mock": "Mocker",
    "service_calls": "list[ServiceCall]",
    "snapshot": "SnapshotAssertion",
    "socket_enabled": "None",
    "tmp_path": "Path",
    "tmpdir": "py.path.local",
    "tts_mutagen_mock": "MagicMock",
    "unused_tcp_port_factory": "Callable[[], int]",
    "unused_udp_port_factory": "Callable[[], int]",
}


_FUNCTION_MATCH: dict[str, list[TypeHintMatch]] = {
    Module.INIT: [
        TypeHintMatch(
            function_name="setup",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigType",
            },
            return_type="bool",
            has_async_counterpart=True,
            mandatory=True,
        ),
        TypeHintMatch(
            function_name="async_setup_entry",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigEntry",
            },
            return_type="bool",
            mandatory=True,
        ),
        TypeHintMatch(
            function_name="async_remove_entry",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigEntry",
            },
            return_type=None,
            mandatory=True,
        ),
        TypeHintMatch(
            function_name="async_unload_entry",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigEntry",
            },
            return_type="bool",
            mandatory=True,
        ),
        TypeHintMatch(
            function_name="async_migrate_entry",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigEntry",
            },
            return_type="bool",
            mandatory=True,
        ),
        TypeHintMatch(
            function_name="async_remove_config_entry_device",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigEntry",
                2: "DeviceEntry",
            },
            return_type="bool",
            mandatory=True,
        ),
        TypeHintMatch(
            function_name="async_reset_platform",
            arg_types={
                0: "HomeAssistant",
                1: "str",
            },
            return_type=None,
            mandatory=True,
        ),
    ],
    ANY_PLATFORM: [
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
            mandatory=True,
        ),
        TypeHintMatch(
            function_name="async_setup_entry",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigEntry",
                2: "AddConfigEntryEntitiesCallback",
            },
            return_type=None,
            mandatory=True,
        ),
    ],
    Module.APPLICATION_CREDENTIALS: [
        TypeHintMatch(
            function_name="async_get_auth_implementation",
            arg_types={
                0: "HomeAssistant",
                1: "str",
                2: "ClientCredential",
            },
            return_type="AbstractOAuth2Implementation",
            mandatory=True,
        ),
        TypeHintMatch(
            function_name="async_get_authorization_server",
            arg_types={
                0: "HomeAssistant",
            },
            return_type="AuthorizationServer",
            mandatory=True,
        ),
    ],
    Module.BACKUP: [
        TypeHintMatch(
            function_name="async_pre_backup",
            arg_types={
                0: "HomeAssistant",
            },
            return_type=None,
            mandatory=True,
        ),
        TypeHintMatch(
            function_name="async_post_backup",
            arg_types={
                0: "HomeAssistant",
            },
            return_type=None,
            mandatory=True,
        ),
    ],
    Module.CAST: [
        TypeHintMatch(
            function_name="async_get_media_browser_root_object",
            arg_types={
                0: "HomeAssistant",
                1: "str",
            },
            return_type="list[BrowseMedia]",
            mandatory=True,
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
            mandatory=True,
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
            mandatory=True,
        ),
    ],
    Module.CONFIG_FLOW: [
        TypeHintMatch(
            function_name="_async_has_devices",
            arg_types={
                0: "HomeAssistant",
            },
            return_type="bool",
            mandatory=True,
        ),
    ],
    Module.DEVICE_ACTION: [
        TypeHintMatch(
            function_name="async_validate_action_config",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigType",
            },
            return_type="ConfigType",
            mandatory=True,
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
            mandatory=True,
        ),
        TypeHintMatch(
            function_name="async_get_action_capabilities",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigType",
            },
            return_type="dict[str, Schema]",
            mandatory=True,
        ),
        TypeHintMatch(
            function_name="async_get_actions",
            arg_types={
                0: "HomeAssistant",
                1: "str",
            },
            return_type=["list[dict[str, str]]", "list[dict[str, Any]]"],
            mandatory=True,
        ),
    ],
    Module.DEVICE_CONDITION: [
        TypeHintMatch(
            function_name="async_validate_condition_config",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigType",
            },
            return_type="ConfigType",
            mandatory=True,
        ),
        TypeHintMatch(
            function_name="async_condition_from_config",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigType",
            },
            return_type="ConditionCheckerType",
            mandatory=True,
        ),
        TypeHintMatch(
            function_name="async_get_condition_capabilities",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigType",
            },
            return_type="dict[str, Schema]",
            mandatory=True,
        ),
        TypeHintMatch(
            function_name="async_get_conditions",
            arg_types={
                0: "HomeAssistant",
                1: "str",
            },
            return_type=["list[dict[str, str]]", "list[dict[str, Any]]"],
            mandatory=True,
        ),
    ],
    Platform.DEVICE_TRACKER: [
        TypeHintMatch(
            function_name="setup_scanner",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigType",
                2: "SeeCallback",
                3: "DiscoveryInfoType | None",
            },
            return_type="bool",
            mandatory=True,
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
            mandatory=True,
        ),
        TypeHintMatch(
            function_name="get_scanner",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigType",
            },
            return_type=["DeviceScanner", None],
            has_async_counterpart=True,
            mandatory=True,
        ),
    ],
    Module.DEVICE_TRIGGER: [
        TypeHintMatch(
            function_name="async_validate_condition_config",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigType",
            },
            return_type="ConfigType",
            mandatory=True,
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
            mandatory=True,
        ),
        TypeHintMatch(
            function_name="async_get_trigger_capabilities",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigType",
            },
            return_type="dict[str, Schema]",
            mandatory=True,
        ),
        TypeHintMatch(
            function_name="async_get_triggers",
            arg_types={
                0: "HomeAssistant",
                1: "str",
            },
            return_type=["list[dict[str, str]]", "list[dict[str, Any]]"],
            mandatory=True,
        ),
    ],
    Module.DIAGNOSTICS: [
        TypeHintMatch(
            function_name="async_get_config_entry_diagnostics",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigEntry",
            },
            return_type="Mapping[str, Any]",
            mandatory=True,
        ),
        TypeHintMatch(
            function_name="async_get_device_diagnostics",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigEntry",
                2: "DeviceEntry",
            },
            return_type="Mapping[str, Any]",
            mandatory=True,
        ),
    ],
    Platform.NOTIFY: [
        TypeHintMatch(
            function_name="get_service",
            arg_types={
                0: "HomeAssistant",
                1: "ConfigType",
                2: "DiscoveryInfoType | None",
            },
            return_type=["BaseNotificationService", None],
            has_async_counterpart=True,
            mandatory=True,
        ),
    ],
}


_CLASS_MATCH: dict[str, list[ClassTypeHintMatch]] = {
    Module.CONFIG_FLOW: [
        ClassTypeHintMatch(
            base_class="FlowHandler",
            exclude_base_classes={"ConfigEntryBaseFlow"},
            matches=[
                TypeHintMatch(
                    function_name="async_step_*",
                    arg_types={},
                    return_type="FlowResult",
                    mandatory=True,
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
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="async_step_dhcp",
                    arg_types={
                        1: "DhcpServiceInfo",
                    },
                    return_type="ConfigFlowResult",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="async_step_hassio",
                    arg_types={
                        1: "HassioServiceInfo",
                    },
                    return_type="ConfigFlowResult",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="async_step_homekit",
                    arg_types={
                        1: "ZeroconfServiceInfo",
                    },
                    return_type="ConfigFlowResult",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="async_step_mqtt",
                    arg_types={
                        1: "MqttServiceInfo",
                    },
                    return_type="ConfigFlowResult",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="async_step_reauth",
                    arg_types={
                        1: "Mapping[str, Any]",
                    },
                    return_type="ConfigFlowResult",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="async_step_ssdp",
                    arg_types={
                        1: "SsdpServiceInfo",
                    },
                    return_type="ConfigFlowResult",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="async_step_usb",
                    arg_types={
                        1: "UsbServiceInfo",
                    },
                    return_type="ConfigFlowResult",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="async_step_zeroconf",
                    arg_types={
                        1: "ZeroconfServiceInfo",
                    },
                    return_type="ConfigFlowResult",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="async_step_*",
                    arg_types={},
                    return_type="ConfigFlowResult",
                    mandatory=True,
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
                    mandatory=True,
                ),
            ],
        ),
        ClassTypeHintMatch(
            base_class="ConfigSubentryFlow",
            matches=[
                TypeHintMatch(
                    function_name="async_step_*",
                    arg_types={},
                    return_type="SubentryFlowResult",
                    mandatory=True,
                ),
            ],
        ),
    ],
    "repairs": [
        ClassTypeHintMatch(
            base_class="RepairsFlow",
            matches=[
                TypeHintMatch(
                    function_name="async_step_*",
                    arg_types={},
                    return_type="RepairsFlowResult",
                    mandatory=True,
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
        mandatory=True,
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
        mandatory=True,
    ),
    TypeHintMatch(
        function_name="state_attributes",
        return_type=["dict[str, Any]", None],
        mandatory=True,
    ),
    TypeHintMatch(
        function_name="extra_state_attributes",
        return_type=["Mapping[str, Any]", None],
        mandatory=True,
    ),
    TypeHintMatch(
        function_name="device_info",
        return_type=["DeviceInfo", None],
        mandatory=True,
    ),
    TypeHintMatch(
        function_name="device_class",
        return_type=["str", None],
        mandatory=True,
    ),
    TypeHintMatch(
        function_name="unit_of_measurement",
        return_type=["str", None],
    ),
    TypeHintMatch(
        function_name="icon",
        return_type=["str", None],
        mandatory=True,
    ),
    TypeHintMatch(
        function_name="entity_picture",
        return_type=["str", None],
    ),
    TypeHintMatch(
        function_name="available",
        return_type="bool",
        mandatory=True,
    ),
    TypeHintMatch(
        function_name="assumed_state",
        return_type="bool",
        mandatory=True,
    ),
    TypeHintMatch(
        function_name="force_update",
        return_type="bool",
        mandatory=True,
    ),
    TypeHintMatch(
        function_name="supported_features",
        return_type=["int", None],
    ),
    TypeHintMatch(
        function_name="entity_registry_enabled_default",
        return_type="bool",
        mandatory=True,
    ),
    TypeHintMatch(
        function_name="entity_registry_visible_default",
        return_type="bool",
        mandatory=True,
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
        mandatory=True,
    ),
    TypeHintMatch(
        function_name="async_added_to_hass",
        return_type=None,
        mandatory=True,
    ),
    TypeHintMatch(
        function_name="async_will_remove_from_hass",
        return_type=None,
        mandatory=True,
    ),
    TypeHintMatch(
        function_name="async_registry_entry_updated",
        return_type=None,
        mandatory=True,
    ),
    TypeHintMatch(
        function_name="update",
        return_type=None,
        has_async_counterpart=True,
        mandatory=True,
    ),
]
_RESTORE_ENTITY_MATCH: list[TypeHintMatch] = [
    TypeHintMatch(
        function_name="async_get_last_state",
        return_type=["State", None],
        mandatory=True,
    ),
    TypeHintMatch(
        function_name="async_get_last_extra_data",
        return_type=["ExtraStoredData", None],
        mandatory=True,
    ),
    TypeHintMatch(
        function_name="extra_restore_state_data",
        return_type=["ExtraStoredData", None],
        mandatory=True,
    ),
]
_TOGGLE_ENTITY_MATCH: list[TypeHintMatch] = [
    TypeHintMatch(
        function_name="is_on",
        return_type=["bool", None],
        mandatory=True,
    ),
    TypeHintMatch(
        function_name="turn_on",
        kwargs_type="Any",
        return_type=None,
        has_async_counterpart=True,
        mandatory=True,
    ),
    TypeHintMatch(
        function_name="turn_off",
        kwargs_type="Any",
        return_type=None,
        has_async_counterpart=True,
        mandatory=True,
    ),
    TypeHintMatch(
        function_name="toggle",
        kwargs_type="Any",
        return_type=None,
        has_async_counterpart=True,
        mandatory=True,
    ),
]
_INHERITANCE_MATCH: dict[str, list[ClassTypeHintMatch]] = {
    # "air_quality": [],  # ignored as deprecated
    Platform.ALARM_CONTROL_PANEL: [
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
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="supported_features",
                    return_type="AlarmControlPanelEntityFeature",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="alarm_disarm",
                    named_arg_types={
                        "code": "str | None",
                    },
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="alarm_arm_home",
                    named_arg_types={
                        "code": "str | None",
                    },
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="alarm_arm_away",
                    named_arg_types={
                        "code": "str | None",
                    },
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="alarm_arm_night",
                    named_arg_types={
                        "code": "str | None",
                    },
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="alarm_arm_vacation",
                    named_arg_types={
                        "code": "str | None",
                    },
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="alarm_trigger",
                    named_arg_types={
                        "code": "str | None",
                    },
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="alarm_arm_custom_bypass",
                    named_arg_types={
                        "code": "str | None",
                    },
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
                ),
            ],
        ),
    ],
    Platform.BINARY_SENSOR: [
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
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="is_on",
                    return_type=["bool", None],
                    mandatory=True,
                ),
            ],
        ),
    ],
    Platform.BUTTON: [
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
                    return_type=["ButtonDeviceClass", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="press",
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
                ),
            ],
        ),
    ],
    Platform.CALENDAR: [
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
                    mandatory=True,
                ),
            ],
        ),
    ],
    Platform.CAMERA: [
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
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="supported_features",
                    return_type="CameraEntityFeature",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="is_recording",
                    return_type="bool",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="is_streaming",
                    return_type="bool",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="brand",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="motion_detection_enabled",
                    return_type="bool",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="model",
                    return_type=["str", None],
                ),
                TypeHintMatch(
                    function_name="frame_interval",
                    return_type="float",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="frontend_stream_type",
                    return_type=["StreamType", None],
                ),
                TypeHintMatch(
                    function_name="available",
                    return_type="bool",
                    mandatory=True,
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
                    mandatory=True,
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
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="turn_off",
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="turn_on",
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="enable_motion_detection",
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="disable_motion_detection",
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="async_handle_async_webrtc_offer",
                    arg_types={
                        1: "str",
                        2: "str",
                        3: "WebRTCSendMessage",
                    },
                    return_type=None,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="async_on_webrtc_candidate",
                    arg_types={
                        1: "str",
                        2: "RTCIceCandidateInit",
                    },
                    return_type=None,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="close_webrtc_session",
                    arg_types={
                        1: "str",
                    },
                    return_type=None,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="_async_get_webrtc_client_configuration",
                    return_type="WebRTCClientConfiguration",
                    mandatory=True,
                ),
            ],
        ),
    ],
    Platform.CLIMATE: [
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
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="temperature_unit",
                    return_type="str",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="current_humidity",
                    return_type=["float", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="target_humidity",
                    return_type=["float", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="hvac_mode",
                    return_type=["HVACMode", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="hvac_modes",
                    return_type="list[HVACMode]",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="hvac_action",
                    return_type=["HVACAction", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="current_temperature",
                    return_type=["float", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="target_temperature",
                    return_type=["float", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="target_temperature_step",
                    return_type=["float", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="target_temperature_high",
                    return_type=["float", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="target_temperature_low",
                    return_type=["float", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="preset_mode",
                    return_type=["str", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="preset_modes",
                    return_type=["list[str]", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="is_aux_heat",
                    return_type=["bool", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="fan_mode",
                    return_type=["str", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="fan_modes",
                    return_type=["list[str]", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="swing_mode",
                    return_type=["str", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="swing_modes",
                    return_type=["list[str]", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="set_temperature",
                    kwargs_type="Any",
                    return_type="None",
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="set_humidity",
                    arg_types={
                        1: "int",
                    },
                    return_type="None",
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="set_fan_mode",
                    arg_types={
                        1: "str",
                    },
                    return_type="None",
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="set_hvac_mode",
                    arg_types={
                        1: "HVACMode",
                    },
                    return_type="None",
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="set_swing_mode",
                    arg_types={
                        1: "str",
                    },
                    return_type="None",
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="set_preset_mode",
                    arg_types={
                        1: "str",
                    },
                    return_type="None",
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="turn_aux_heat_on",
                    return_type="None",
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="turn_aux_heat_off",
                    return_type="None",
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="turn_on",
                    return_type="None",
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="turn_off",
                    return_type="None",
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="supported_features",
                    return_type="ClimateEntityFeature",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="min_temp",
                    return_type="float",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="max_temp",
                    return_type="float",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="min_humidity",
                    return_type="float",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="max_humidity",
                    return_type="float",
                    mandatory=True,
                ),
            ],
        ),
    ],
    Platform.COVER: [
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
                    mandatory=True,
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
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="open_cover",
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="close_cover",
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="toggle",
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="set_cover_position",
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="stop_cover",
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="open_cover_tilt",
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="close_cover_tilt",
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="set_cover_tilt_position",
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="stop_cover_tilt",
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="toggle_tilt",
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
                ),
            ],
        ),
    ],
    Platform.DEVICE_TRACKER: [
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
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="source_type",
                    return_type="SourceType",
                    mandatory=True,
                ),
            ],
        ),
        ClassTypeHintMatch(
            base_class="TrackerEntity",
            matches=[
                TypeHintMatch(
                    function_name="force_update",
                    return_type="bool",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="location_accuracy",
                    return_type="float",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="location_name",
                    return_type=["str", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="latitude",
                    return_type=["float", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="longitude",
                    return_type=["float", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="state",
                    return_type=["str", None],
                    mandatory=True,
                ),
            ],
        ),
        ClassTypeHintMatch(
            base_class="ScannerEntity",
            matches=[
                TypeHintMatch(
                    function_name="ip_address",
                    return_type=["str", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="mac_address",
                    return_type=["str", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="hostname",
                    return_type=["str", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="state",
                    return_type="str",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="is_connected",
                    return_type="bool",
                    mandatory=True,
                ),
            ],
        ),
    ],
    Module.ENTITY: [
        ClassTypeHintMatch(
            base_class="Entity",
            matches=_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="RestoreEntity",
            matches=_RESTORE_ENTITY_MATCH,
        ),
    ],
    Platform.FAN: [
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
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="speed_count",
                    return_type="int",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="percentage_step",
                    return_type="float",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="current_direction",
                    return_type=["str", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="oscillating",
                    return_type=["bool", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="preset_mode",
                    return_type=["str", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="preset_modes",
                    return_type=["list[str]", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="supported_features",
                    return_type="FanEntityFeature",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="set_percentage",
                    arg_types={1: "int"},
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="set_preset_mode",
                    arg_types={1: "str"},
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="set_direction",
                    arg_types={1: "str"},
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
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
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="oscillate",
                    arg_types={1: "bool"},
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
                ),
            ],
        ),
    ],
    Platform.GEO_LOCATION: [
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
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="distance",
                    return_type=["float", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="latitude",
                    return_type=["float", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="longitude",
                    return_type=["float", None],
                    mandatory=True,
                ),
            ],
        ),
    ],
    Platform.IMAGE_PROCESSING: [
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
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="confidence",
                    return_type=["float", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="device_class",
                    return_type=["ImageProcessingDeviceClass", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="process_image",
                    arg_types={1: "bytes"},
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
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
                    mandatory=True,
                ),
            ],
        ),
    ],
    Platform.HUMIDIFIER: [
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
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="device_class",
                    return_type=["HumidifierDeviceClass", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="min_humidity",
                    return_type=["float"],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="max_humidity",
                    return_type=["float"],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="mode",
                    return_type=["str", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="supported_features",
                    return_type="HumidifierEntityFeature",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="target_humidity",
                    return_type=["float", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="set_humidity",
                    arg_types={1: "int"},
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="set_mode",
                    arg_types={1: "str"},
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
                ),
            ],
        ),
    ],
    Platform.LIGHT: [
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
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="color_mode",
                    return_type=["ColorMode", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="hs_color",
                    return_type=["tuple[float, float]", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="xy_color",
                    return_type=["tuple[float, float]", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="rgb_color",
                    return_type=["tuple[int, int, int]", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="rgbw_color",
                    return_type=["tuple[int, int, int, int]", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="rgbww_color",
                    return_type=["tuple[int, int, int, int, int]", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="color_temp_kelvin",
                    return_type=["int", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="max_color_temp_kelvin",
                    return_type="int",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="min_color_temp_kelvin",
                    return_type="int",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="effect_list",
                    return_type=["list[str]", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="effect",
                    return_type=["str", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="capability_attributes",
                    return_type=["dict[str, Any]", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="supported_color_modes",
                    return_type=["set[ColorMode]", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="supported_features",
                    return_type="LightEntityFeature",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="turn_on",
                    named_arg_types={
                        "brightness": "int | None",
                        "brightness_pct": "float | None",
                        "brightness_step": "int | None",
                        "brightness_step_pct": "float | None",
                        "color_name": "str | None",
                        "color_temp_kelvin": "int | None",
                        "effect": "str | None",
                        "flash": "str | None",
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
                    mandatory=True,
                ),
            ],
        ),
    ],
    Platform.LOCK: [
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
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="code_format",
                    return_type=["str", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="is_locked",
                    return_type=["bool", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="is_locking",
                    return_type=["bool", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="is_unlocking",
                    return_type=["bool", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="is_jammed",
                    return_type=["bool", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="supported_features",
                    return_type="LockEntityFeature",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="lock",
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="unlock",
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="open",
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
                ),
            ],
        ),
    ],
    Platform.MEDIA_PLAYER: [
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
                    mandatory=True,
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
    Platform.NOTIFY: [
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
                    mandatory=True,
                ),
            ],
        ),
    ],
    Platform.NUMBER: [
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
                    mandatory=True,
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
    Platform.REMOTE: [
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
    Platform.SCENE: [
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
    Platform.SELECT: [
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
    Platform.SENSOR: [
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
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="state_class",
                    return_type=["SensorStateClass", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="last_reset",
                    return_type=["datetime", None],
                    mandatory=True,
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
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="async_get_last_sensor_data",
                    return_type=["SensorExtraStoredData", None],
                    mandatory=True,
                ),
            ],
        ),
    ],
    Platform.SIREN: [
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
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="supported_features",
                    return_type="SirenEntityFeature",
                    mandatory=True,
                ),
            ],
        ),
    ],
    Platform.STT: [
        ClassTypeHintMatch(
            base_class="Provider",
            matches=[
                TypeHintMatch(
                    function_name="supported_languages",
                    return_type="list[str]",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="supported_formats",
                    return_type="list[AudioFormats]",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="supported_codecs",
                    return_type="list[AudioCodecs]",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="supported_bit_rates",
                    return_type="list[AudioBitRates]",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="supported_sample_rates",
                    return_type="list[AudioSampleRates]",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="supported_channels",
                    return_type="list[AudioChannels]",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="async_process_audio_stream",
                    arg_types={1: "SpeechMetadata", 2: "AsyncIterable[bytes]"},
                    return_type="SpeechResult",
                    mandatory=True,
                ),
            ],
        ),
    ],
    Platform.SWITCH: [
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
                    mandatory=True,
                ),
            ],
        ),
    ],
    Platform.TODO: [
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
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="async_create_todo_item",
                    arg_types={
                        1: "TodoItem",
                    },
                    return_type="None",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="async_update_todo_item",
                    arg_types={
                        1: "TodoItem",
                    },
                    return_type="None",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="async_delete_todo_items",
                    arg_types={
                        1: "list[str]",
                    },
                    return_type="None",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="async_move_todo_item",
                    arg_types={
                        1: "str",
                        2: "str | None",
                    },
                    return_type="None",
                    mandatory=True,
                ),
            ],
        ),
    ],
    Platform.TTS: [
        ClassTypeHintMatch(
            base_class="Provider",
            matches=[
                TypeHintMatch(
                    function_name="default_language",
                    return_type=["str", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="supported_languages",
                    return_type=["list[str]", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="supported_options",
                    return_type=["list[str]", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="default_options",
                    return_type=["Mapping[str, Any]", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="get_tts_audio",
                    arg_types={1: "str", 2: "str", 3: "dict[str, Any]"},
                    return_type="TtsAudioType",
                    has_async_counterpart=True,
                    mandatory=True,
                ),
            ],
        ),
    ],
    Platform.UPDATE: [
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
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="installed_version",
                    return_type=["str", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="device_class",
                    return_type=["UpdateDeviceClass", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="in_progress",
                    return_type=["bool", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="latest_version",
                    return_type=["str", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="release_summary",
                    return_type=["str", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="release_url",
                    return_type=["str", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="supported_features",
                    return_type="UpdateEntityFeature",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="title",
                    return_type=["str", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="update_percentage",
                    return_type=["int", "float", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="install",
                    arg_types={1: "str | None", 2: "bool"},
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="release_notes",
                    return_type=["str", None],
                    has_async_counterpart=True,
                    mandatory=True,
                ),
            ],
        ),
    ],
    Platform.VACUUM: [
        ClassTypeHintMatch(
            base_class="Entity",
            matches=_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="RestoreEntity",
            matches=_RESTORE_ENTITY_MATCH,
        ),
        ClassTypeHintMatch(
            base_class="StateVacuumEntity",
            matches=[
                TypeHintMatch(
                    function_name="state",
                    return_type=["str", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="activity",
                    return_type=["VacuumActivity", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="battery_level",
                    return_type=["int", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="battery_icon",
                    return_type="str",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="fan_speed",
                    return_type=["str", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="fan_speed_list",
                    return_type="list[str]",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="supported_features",
                    return_type="VacuumEntityFeature",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="stop",
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="start",
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="pause",
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="return_to_base",
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="clean_spot",
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="locate",
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="set_fan_speed",
                    named_arg_types={
                        "fan_speed": "str",
                    },
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
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
                    mandatory=True,
                ),
            ],
        ),
    ],
    Platform.WATER_HEATER: [
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
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="current_temperature",
                    return_type=["float", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="is_away_mode_on",
                    return_type=["bool", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="max_temp",
                    return_type="float",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="min_temp",
                    return_type="float",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="operation_list",
                    return_type=["list[str]", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="precision",
                    return_type="float",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="supported_features",
                    return_type="WaterHeaterEntityFeature",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="target_temperature",
                    return_type=["float", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="target_temperature_high",
                    return_type=["float", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="target_temperature_low",
                    return_type=["float", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="temperature_unit",
                    return_type="str",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="set_temperature",
                    kwargs_type="Any",
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="set_operation_mode",
                    arg_types={1: "str"},
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="turn_away_mode_on",
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="turn_away_mode_off",
                    return_type=None,
                    has_async_counterpart=True,
                    mandatory=True,
                ),
            ],
        ),
    ],
    Platform.WEATHER: [
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
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="native_temperature_unit",
                    return_type=["str", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="native_pressure",
                    return_type=["float", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="native_pressure_unit",
                    return_type=["str", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="humidity",
                    return_type=["float", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="native_wind_gust_speed",
                    return_type=["float", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="native_wind_speed",
                    return_type=["float", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="native_wind_speed_unit",
                    return_type=["str", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="wind_bearing",
                    return_type=["float", "str", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="ozone",
                    return_type=["float", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="native_visibility",
                    return_type=["float", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="native_visibility_unit",
                    return_type=["str", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="forecast",
                    return_type=["list[Forecast]", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="native_precipitation_unit",
                    return_type=["str", None],
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="precision",
                    return_type="float",
                    mandatory=True,
                ),
                TypeHintMatch(
                    function_name="condition",
                    return_type=["str", None],
                    mandatory=True,
                ),
            ],
        ),
    ],
}
