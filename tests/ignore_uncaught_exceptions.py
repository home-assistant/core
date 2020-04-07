"""List of modules that have uncaught exceptions today. Will be shrunk over time."""
IGNORE_UNCAUGHT_EXCEPTIONS = [
    ("tests.components.demo.test_init", "test_setting_up_demo"),
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
    ("tests.components.qwikswitch.test_init", "test_binary_sensor_device"),
    ("tests.components.qwikswitch.test_init", "test_sensor_device"),
    ("tests.components.rflink.test_init", "test_send_command_invalid_arguments"),
]

IGNORE_UNCAUGHT_JSON_EXCEPTIONS = []
