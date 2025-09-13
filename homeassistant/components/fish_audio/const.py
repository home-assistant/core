"""Constants for the FishAudio integration."""

from typing import Literal

DOMAIN = "fish_audio"


CONF_NAME: Literal["name"] = "name"
CONF_USER_ID: Literal["user_id"] = "user_id"
CONF_API_KEY: Literal["api_key"] = "api_key"
CONF_VOICE_ID: Literal["voice_id"] = "voice_id"
CONF_BACKEND: Literal["backend"] = "backend"
CONF_SELF_ONLY: Literal["self_only"] = "self_only"
CONF_LANGUAGE: Literal["language"] = "language"
CONF_SORT_BY: Literal["sort_by"] = "sort_by"

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
