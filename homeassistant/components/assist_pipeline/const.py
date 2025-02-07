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

SAMPLE_RATE = 16000  # hertz
SAMPLE_WIDTH = 2  # bytes
SAMPLE_CHANNELS = 1  # mono
MS_PER_CHUNK = 10
SAMPLES_PER_CHUNK = SAMPLE_RATE // (1000 // MS_PER_CHUNK)  # 10 ms @ 16Khz
BYTES_PER_CHUNK = SAMPLES_PER_CHUNK * SAMPLE_WIDTH * SAMPLE_CHANNELS  # 16-bit

OPTION_PREFERRED = "preferred"
