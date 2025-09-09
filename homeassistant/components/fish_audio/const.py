"""Constants for the FishAudio integration."""

DOMAIN = "fish_audio"

CONF_API_KEY = "api_key"
CONF_VOICE_ID = "voice_id"
CONF_BACKEND = "backend"
CONF_SELF_ONLY = "self_only"
CONF_LANGUAGE = "language"
CONF_SORT_BY = "sort_by"
WARNING_CREDIT_BALANCE = 1
CRITICAL_CREDIT_BALANCE = 0.5

DEVELOPER_ID = "1e9f9baadce144f5b16dd94cbc0314c8"

LANGUAGE_OPTIONS = [
    {"value": "en", "label": "English"},
    {"value": "zh", "label": "Chinese"},
    {"value": "de", "label": "German"},
    {"value": "ja", "label": "Japanese"},
    {"value": "ar", "label": "Arabic"},
    {"value": "fr", "label": "French"},
    {"value": "es", "label": "Spanish"},
    {"value": "ko", "label": "Korean"},
]
TTS_SUPPORTED_LANGUAGES = [
    "ar",
    "de",
    "en",
    "es",
    "fr",
    "ja",
    "ko",
    "zh",
]

STT_SUPPORTED_LANGUAGES = [
    "",  # Auto Detect
    "ar",
    "de",
    "en",
    "es",
    "fr",
    "ja",
    "ko",
    "zh",
]

BACKEND_MODELS = ["s1", "s1-mini", "speech-1.5", "speech-1.6"]
SORT_BY_OPTIONS = ["score", "task_count", "created_at"]
