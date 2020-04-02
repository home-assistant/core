"""List of modules that have uncaught exceptions today. Will be shrunk over time."""
IGNORE_UNCAUGHT_EXCEPTIONS = [
    ("tests.components.cast.test_media_player", "test_start_discovery_called_once"),
    ("tests.components.cast.test_media_player", "test_entry_setup_single_config"),
    ("tests.components.cast.test_media_player", "test_entry_setup_list_config"),
    ("tests.components.cast.test_media_player", "test_entry_setup_platform_not_ready"),
    ("tests.components.config.test_group", "test_update_device_config"),
    ("tests.components.default_config.test_init", "test_setup"),
    ("tests.components.demo.test_init", "test_setting_up_demo"),
    ("tests.components.discovery.test_init", "test_discover_config_flow"),
    ("tests.components.dsmr.test_sensor", "test_default_setup"),
    ("tests.components.dsmr.test_sensor", "test_v4_meter"),
    ("tests.components.dsmr.test_sensor", "test_v5_meter"),
    ("tests.components.dsmr.test_sensor", "test_belgian_meter"),
    ("tests.components.dsmr.test_sensor", "test_belgian_meter_low"),
    ("tests.components.dsmr.test_sensor", "test_tcp"),
    ("tests.components.dsmr.test_sensor", "test_connection_errors_retry"),
    ("tests.components.dyson.test_air_quality", "test_purecool_aiq_attributes"),
    ("tests.components.dyson.test_air_quality", "test_purecool_aiq_update_state"),
    (
        "tests.components.dyson.test_air_quality",
        "test_purecool_component_setup_only_once",
    ),
    ("tests.components.dyson.test_air_quality", "test_purecool_aiq_without_discovery"),
    (
        "tests.components.dyson.test_air_quality",
        "test_purecool_aiq_empty_environment_state",
    ),
    (
        "tests.components.dyson.test_climate",
        "test_setup_component_with_parent_discovery",
    ),
    ("tests.components.dyson.test_fan", "test_purecoollink_attributes"),
    ("tests.components.dyson.test_fan", "test_purecool_turn_on"),
    ("tests.components.dyson.test_fan", "test_purecool_set_speed"),
    ("tests.components.dyson.test_fan", "test_purecool_turn_off"),
    ("tests.components.dyson.test_fan", "test_purecool_set_dyson_speed"),
    ("tests.components.dyson.test_fan", "test_purecool_oscillate"),
    ("tests.components.dyson.test_fan", "test_purecool_set_night_mode"),
    ("tests.components.dyson.test_fan", "test_purecool_set_auto_mode"),
    ("tests.components.dyson.test_fan", "test_purecool_set_angle"),
    ("tests.components.dyson.test_fan", "test_purecool_set_flow_direction_front"),
    ("tests.components.dyson.test_fan", "test_purecool_set_timer"),
    ("tests.components.dyson.test_fan", "test_purecool_update_state"),
    ("tests.components.dyson.test_fan", "test_purecool_update_state_filter_inv"),
    ("tests.components.dyson.test_fan", "test_purecool_component_setup_only_once"),
    ("tests.components.dyson.test_sensor", "test_purecool_component_setup_only_once"),
    ("tests.components.ios.test_init", "test_creating_entry_sets_up_sensor"),
    ("tests.components.ios.test_init", "test_not_configuring_ios_not_creates_entry"),
    ("tests.components.local_file.test_camera", "test_file_not_readable"),
    (
        "tests.components.mqtt.test_init",
        "test_setup_uses_certificate_on_certificate_set_to_auto",
    ),
    (
        "tests.components.mqtt.test_init",
        "test_setup_does_not_use_certificate_on_mqtts_port",
    ),
    (
        "tests.components.mqtt.test_init",
        "test_setup_without_tls_config_uses_tlsv1_under_python36",
    ),
    (
        "tests.components.mqtt.test_init",
        "test_setup_with_tls_config_uses_tls_version1_2",
    ),
    (
        "tests.components.mqtt.test_init",
        "test_setup_with_tls_config_of_v1_under_python36_only_uses_v1",
    ),
    ("tests.components.qwikswitch.test_init", "test_binary_sensor_device"),
    ("tests.components.qwikswitch.test_init", "test_sensor_device"),
    ("tests.components.rflink.test_init", "test_send_command_invalid_arguments"),
    ("tests.components.samsungtv.test_media_player", "test_update_connection_failure"),
    (
        "tests.components.tplink.test_init",
        "test_configuring_devices_from_multiple_sources",
    ),
    ("tests.components.unifi_direct.test_device_tracker", "test_get_scanner"),
    ("tests.components.upnp.test_init", "test_async_setup_entry_default"),
    ("tests.components.upnp.test_init", "test_async_setup_entry_port_mapping"),
    ("tests.components.yr.test_sensor", "test_default_setup"),
    ("tests.components.yr.test_sensor", "test_custom_setup"),
    ("tests.components.yr.test_sensor", "test_forecast_setup"),
    ("tests.components.zwave.test_init", "test_power_schemes"),
]

IGNORE_UNCAUGHT_JSON_EXCEPTIONS = [
    ("tests.components.spotify.test_config_flow", "test_full_flow"),
    ("tests.components.smartthings.test_init", "test_config_entry_loads_platforms"),
    (
        "tests.components.smartthings.test_init",
        "test_scenes_unauthorized_loads_platforms",
    ),
    (
        "tests.components.smartthings.test_init",
        "test_config_entry_loads_unconnected_cloud",
    ),
    ("tests.components.samsungtv.test_config_flow", "test_ssdp"),
    ("tests.components.samsungtv.test_config_flow", "test_user_websocket"),
    ("tests.components.samsungtv.test_config_flow", "test_user_already_configured"),
    ("tests.components.samsungtv.test_config_flow", "test_autodetect_websocket"),
    ("tests.components.samsungtv.test_config_flow", "test_autodetect_websocket_ssl"),
    ("tests.components.samsungtv.test_config_flow", "test_ssdp_already_configured"),
    ("tests.components.samsungtv.test_config_flow", "test_ssdp_noprefix"),
    ("tests.components.samsungtv.test_config_flow", "test_user_legacy"),
    ("tests.components.samsungtv.test_config_flow", "test_autodetect_legacy"),
    (
        "tests.components.samsungtv.test_media_player",
        "test_select_source_invalid_source",
    ),
    (
        "tests.components.samsungtv.test_media_player",
        "test_play_media_channel_as_string",
    ),
    (
        "tests.components.samsungtv.test_media_player",
        "test_play_media_channel_as_non_positive",
    ),
    ("tests.components.samsungtv.test_media_player", "test_turn_off_websocket"),
    ("tests.components.samsungtv.test_media_player", "test_play_media_invalid_type"),
    ("tests.components.harmony.test_config_flow", "test_form_import"),
    ("tests.components.harmony.test_config_flow", "test_form_ssdp"),
    ("tests.components.harmony.test_config_flow", "test_user_form"),
]
