"""Constants for the FishAudio integration."""

from typing import Literal

DOMAIN = "fish_audio"

CONF_USER_ID: Literal["user_id"] = "user_id"
CONF_VOICE_ID: Literal["voice_id"] = "voice_id"
CONF_BACKEND: Literal["backend"] = "backend"
CONF_SELF_ONLY: Literal["self_only"] = "self_only"
CONF_SORT_BY: Literal["sort_by"] = "sort_by"
CONF_LATENCY: Literal["latency"] = "latency"
CONF_SPEED: Literal["speed"] = "speed"
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


BACKEND_MODELS = ["s2-pro", "s1", "speech-1.5", "speech-1.6"]
SORT_BY_OPTIONS = ["task_count", "score", "created_at"]
LATENCY_OPTIONS = ["normal", "balanced"]

# Speech speed multiplier accepted by the Fish Audio API (1.0 = normal speed).
DEFAULT_SPEED = 1.0
MIN_SPEED = 0.5
MAX_SPEED = 2.0
SPEED_STEP = 0.05

SIGNUP_URL = "https://fish.audio/"
BILLING_URL = "https://fish.audio/app/billing/"
API_KEYS_URL = "https://fish.audio/app/api-keys/"
