"""Constants for the CAMB AI text-to-speech integration."""

DOMAIN = "camb_tts"

CONF_API_KEY = "api_key"
CONF_VOICE_ID = "voice_id"
CONF_SPEECH_MODEL = "speech_model"

DEFAULT_LANG = "en-us"
DEFAULT_VOICE_ID = 147320
DEFAULT_SPEECH_MODEL = "mars-flash"

SUPPORT_LANGUAGES = [
    "en-us",
    "es-es",
    "fr-fr",
    "de-de",
    "ja-jp",
    "hi-in",
    "pt-br",
    "zh-cn",
    "ko-kr",
    "it-it",
    "nl-nl",
    "ru-ru",
    "ar-sa",
    "ta-in",
    "te-in",
    "bn-in",
]

SUPPORT_SPEECH_MODELS = [
    "mars-flash",
    "mars-pro",
    "mars-instruct",
]
