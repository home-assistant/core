"""List of modules that have uncaught exceptions today. Will be shrunk over time."""
IGNORE_UNCAUGHT_EXCEPTIONS = [
    ("tests.components.ios.test_init", "test_creating_entry_sets_up_sensor"),
    ("tests.components.ios.test_init", "test_not_configuring_ios_not_creates_entry"),
    ("tests.components.local_file.test_camera", "test_file_not_readable"),
]

IGNORE_UNCAUGHT_JSON_EXCEPTIONS = []
