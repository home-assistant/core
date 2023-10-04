"""Constants for the Assist pipeline integration."""
DOMAIN = "assist_pipeline"

DATA_CONFIG = f"{DOMAIN}.config"

CONF_PIPELINE_TIMEOUT = "pipeline_timeout"
DEFAULT_PIPELINE_TIMEOUT = 60 * 5  # seconds

CONF_WAKE_WORD_TIMEOUT = "wake_word_timeout"
DEFAULT_WAKE_WORD_TIMEOUT = 3  # seconds

CONF_DEBUG_RECORDING_DIR = "debug_recording_dir"
