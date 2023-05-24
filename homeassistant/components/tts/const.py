"""Text-to-speech constants."""
ATTR_CACHE = "cache"
ATTR_LANGUAGE = "language"
ATTR_MESSAGE = "message"
ATTR_OPTIONS = "options"

CONF_BASE_URL = "base_url"
CONF_CACHE = "cache"
CONF_CACHE_DIR = "cache_dir"
CONF_FIELDS = "fields"
CONF_TIME_MEMORY = "time_memory"

DEFAULT_CACHE = True
DEFAULT_CACHE_DIR = "tts"
DEFAULT_TIME_MEMORY = 300

DOMAIN = "tts"

DATA_TTS_MANAGER = "tts_manager"

TtsAudioType = tuple[str | None, bytes | None]
