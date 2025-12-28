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
CONF_LATENCY: Literal["latency"] = "latency"
CONF_TITLE: Literal["title"] = "title"

DEVELOPER_ID = "1e9f9baadce144f5b16dd94cbc0314c8"

TTS_SUPPORTED_LANGUAGES = [
    "Any",
    "en",
    "zh",
    "de",
    "ja",
    "ar",
    "fr",
    "es",
    "ko",
]


BACKEND_MODELS = ["s1", "speech-1.5", "speech-1.6"]
SORT_BY_OPTIONS = ["task_count", "score", "created_at"]
LATENCY_OPTIONS = ["normal", "balanced"]

SIGNUP_URL = "https://fish.audio/?fpr=homeassistant"  # codespell:ignore fpr
BILLING_URL = "https://fish.audio/app/billing/"
API_KEYS_URL = "https://fish.audio/app/api-keys/"
