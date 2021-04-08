"""List of tests that have uncaught exceptions today. Will be shrunk over time."""
IGNORE_UNCAUGHT_EXCEPTIONS = [
    (
        "test_homeassistant_bridge",
        "test_homeassistant_bridge_fan_setup",
    ),
    (
        "tests.components.owntracks.test_device_tracker",
        "test_mobile_multiple_async_enter_exit",
    ),
    (
        "tests.components.smartthings.test_init",
        "test_event_handler_dispatches_updated_devices",
    ),
    (
        "tests.components.unifi.test_controller",
        "test_wireless_client_event_calls_update_wireless_devices",
    ),
    ("tests.components.iaqualink.test_config_flow", "test_with_invalid_credentials"),
    ("tests.components.iaqualink.test_config_flow", "test_with_existing_config"),
]
