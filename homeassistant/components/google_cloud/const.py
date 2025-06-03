"""Constants for the Google Cloud component."""

from __future__ import annotations

DOMAIN = "google_cloud"
TITLE = "Google Cloud"

CONF_SERVICE_ACCOUNT_INFO = "service_account_info"
CONF_KEY_FILE = "key_file"

DEFAULT_LANG = "en-US"

# TTS constants
CONF_GENDER = "gender"
CONF_VOICE = "voice"
CONF_ENCODING = "encoding"
CONF_SPEED = "speed"
CONF_PITCH = "pitch"
CONF_GAIN = "gain"
CONF_PROFILES = "profiles"
CONF_TEXT_TYPE = "text_type"

DEFAULT_SPEED = 1.0
DEFAULT_PITCH = 0
DEFAULT_GAIN = 0

# STT constants
CONF_STT_MODEL = "stt_model"

DEFAULT_STT_MODEL = "latest_short"

# https://cloud.google.com/speech-to-text/docs/transcription-model
SUPPORTED_STT_MODELS = [
    "latest_long",
    "latest_short",
    "telephony",
    "telephony_short",
    "medical_dictation",
    "medical_conversation",
    "command_and_search",
    "default",
    "phone_call",
    "video",
]

# https://cloud.google.com/speech-to-text/docs/speech-to-text-supported-languages
STT_LANGUAGES = [
    "af-ZA",
    "am-ET",
    "ar-AE",
    "ar-BH",
    "ar-DZ",
    "ar-EG",
    "ar-IL",
    "ar-IQ",
    "ar-JO",
    "ar-KW",
    "ar-LB",
    "ar-MA",
    "ar-MR",
    "ar-OM",
    "ar-PS",
    "ar-QA",
    "ar-SA",
    "ar-SY",
    "ar-TN",
    "ar-YE",
    "az-AZ",
    "bg-BG",
    "bn-BD",
    "bn-IN",
    "bs-BA",
    "ca-ES",
    "cmn-Hans-CN",
    "cmn-Hans-HK",
    "cmn-Hant-TW",
    "cs-CZ",
    "da-DK",
    "de-AT",
    "de-CH",
    "de-DE",
    "el-GR",
    "en-AU",
    "en-CA",
    "en-GB",
    "en-GH",
    "en-HK",
    "en-IE",
    "en-IN",
    "en-KE",
    "en-NG",
    "en-NZ",
    "en-PH",
    "en-PK",
    "en-SG",
    "en-TZ",
    "en-US",
    "en-ZA",
    "es-AR",
    "es-BO",
    "es-CL",
    "es-CO",
    "es-CR",
    "es-DO",
    "es-EC",
    "es-ES",
    "es-GT",
    "es-HN",
    "es-MX",
    "es-NI",
    "es-PA",
    "es-PE",
    "es-PR",
    "es-PY",
    "es-SV",
    "es-US",
    "es-UY",
    "es-VE",
    "et-EE",
    "eu-ES",
    "fa-IR",
    "fi-FI",
    "fil-PH",
    "fr-BE",
    "fr-CA",
    "fr-CH",
    "fr-FR",
    "gl-ES",
    "gu-IN",
    "hi-IN",
    "hr-HR",
    "hu-HU",
    "hy-AM",
    "id-ID",
    "is-IS",
    "it-CH",
    "it-IT",
    "iw-IL",
    "ja-JP",
    "jv-ID",
    "ka-GE",
    "kk-KZ",
    "km-KH",
    "kn-IN",
    "ko-KR",
    "lo-LA",
    "lt-LT",
    "lv-LV",
    "mk-MK",
    "ml-IN",
    "mn-MN",
    "mr-IN",
    "ms-MY",
    "my-MM",
    "ne-NP",
    "nl-BE",
    "nl-NL",
    "no-NO",
    "pa-Guru-IN",
    "pl-PL",
    "pt-BR",
    "pt-PT",
    "ro-RO",
    "ru-RU",
    "si-LK",
    "sk-SK",
    "sl-SI",
    "sq-AL",
    "sr-RS",
    "su-ID",
    "sv-SE",
    "sw-KE",
    "sw-TZ",
    "ta-IN",
    "ta-LK",
    "ta-MY",
    "ta-SG",
    "te-IN",
    "th-TH",
    "tr-TR",
    "uk-UA",
    "ur-IN",
    "ur-PK",
    "uz-UZ",
    "vi-VN",
    "yue-Hant-HK",
    "zu-ZA",
]
