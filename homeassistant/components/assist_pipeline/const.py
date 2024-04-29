"""Constants for the Assist pipeline integration."""

DOMAIN = "assist_pipeline"

DATA_CONFIG = f"{DOMAIN}.config"
DATA_MIGRATIONS = f"{DOMAIN}_migrations"

DEFAULT_PIPELINE_TIMEOUT = 60 * 5  # seconds

DEFAULT_WAKE_WORD_TIMEOUT = 3  # seconds

CONF_DEBUG_RECORDING_DIR = "debug_recording_dir"

DATA_LAST_WAKE_UP = f"{DOMAIN}.last_wake_up"
WAKE_WORD_COOLDOWN = 2  # seconds

EVENT_RECORDING = f"{DOMAIN}_recording"
