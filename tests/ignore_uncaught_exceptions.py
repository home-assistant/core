"""List of tests that have uncaught exceptions today. Will be shrunk over time."""

IGNORE_UNCAUGHT_EXCEPTIONS = [
    (
        # This test explicitly throws an uncaught exception
        # and should not be removed.
        "tests.test_runner",
        "test_unhandled_exception_traceback",
    ),
    (
        # This test explicitly throws an uncaught exception
        # and should not be removed.
        "tests.helpers.test_event",
        "test_track_point_in_time_repr",
    ),
    (
        # This test explicitly throws an uncaught exception
        # and should not be removed.
        "tests.test_config_entries",
        "test_config_entry_unloaded_during_platform_setups",
    ),
    (
        # This test explicitly throws an uncaught exception
        # and should not be removed.
        "tests.test_config_entries",
        "test_config_entry_unloaded_during_platform_setup",
    ),
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
