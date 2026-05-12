"""Constants for the FlowSpeech integration."""

from typing import Final, Literal

DOMAIN: Final = "flowspeech"
MANUFACTURER: Final = "FlowSpeech"

CONF_API_KEY: Literal["api_key"] = "api_key"
CONF_VOICE: Literal["voice"] = "voice"

DEFAULT_VOICE: Final = "Kore"
SIGNUP_URL: Final = "https://flowspeech.io/"
API_KEYS_URL: Final = "https://flowspeech.io/settings/apikeys"

SUPPORTED_LANGUAGES: Final = [
    "en",
    "ar",
    "de",
    "es",
    "fr",
    "ja",
    "ko",
    "zh",
]

