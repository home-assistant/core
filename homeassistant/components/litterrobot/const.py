"""Constants for the Litter-Robot integration."""

DOMAIN = "litterrobot"

CONF_RECORDING_ENABLED = "recording_enabled"
CONF_RECORDING_DURATION = "recording_duration"
CONF_RECORDING_RETENTION = "recording_retention_days"
CONF_RECORDING_EVENT_TYPES = "recording_event_types"

DEFAULT_RECORDING_DURATION = 30
DEFAULT_RECORDING_RETENTION_DAYS = 30
DEFAULT_RECORDING_EVENT_TYPES = [
    "pet_visit",
    "cat_detect",
    "cycle_completed",
    "cycle_interrupted",
]
