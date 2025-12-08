"""Constants for the ElevenLabs text-to-speech integration."""

ATTR_MODEL = "model"

CONF_VOICE = "voice"
CONF_MODEL = "model"
CONF_CONFIGURE_VOICE = "configure_voice"
CONF_STABILITY = "stability"
CONF_SIMILARITY = "similarity"
CONF_STT_AUTO_LANGUAGE = "stt_auto_language"
CONF_STT_MODEL = "stt_model"
CONF_STYLE = "style"
CONF_USE_SPEAKER_BOOST = "use_speaker_boost"
DOMAIN = "elevenlabs"

DEFAULT_TTS_MODEL = "eleven_multilingual_v2"
DEFAULT_STABILITY = 0.5
DEFAULT_SIMILARITY = 0.75
DEFAULT_STT_AUTO_LANGUAGE = False
DEFAULT_STT_MODEL = "scribe_v2"
DEFAULT_STYLE = 0
DEFAULT_USE_SPEAKER_BOOST = True

MAX_REQUEST_IDS = 3
MODELS_PREVIOUS_INFO_NOT_SUPPORTED = ("eleven_v3",)

STT_LANGUAGES = [
    "af-ZA",  # Afrikaans
    "am-ET",  # Amharic
    "ar-SA",  # Arabic
    "hy-AM",  # Armenian
    "as-IN",  # Assamese
    "ast-ES",  # Asturian
    "az-AZ",  # Azerbaijani
    "be-BY",  # Belarusian
    "bn-IN",  # Bengali
    "bs-BA",  # Bosnian
    "bg-BG",  # Bulgarian
    "my-MM",  # Burmese
    "yue-HK",  # Cantonese
    "ca-ES",  # Catalan
    "ceb-PH",  # Cebuano
    "ny-MW",  # Chichewa
    "hr-HR",  # Croatian
    "cs-CZ",  # Czech
    "da-DK",  # Danish
    "nl-NL",  # Dutch
    "en-US",  # English
    "et-EE",  # Estonian
    "fil-PH",  # Filipino
    "fi-FI",  # Finnish
    "fr-FR",  # French
    "ff-SN",  # Fulah
    "gl-ES",  # Galician
    "lg-UG",  # Ganda
    "ka-GE",  # Georgian
    "de-DE",  # German
    "el-GR",  # Greek
    "gu-IN",  # Gujarati
    "ha-NG",  # Hausa
    "he-IL",  # Hebrew
    "hi-IN",  # Hindi
    "hu-HU",  # Hungarian
    "is-IS",  # Icelandic
    "ig-NG",  # Igbo
    "id-ID",  # Indonesian
    "ga-IE",  # Irish
    "it-IT",  # Italian
    "ja-JP",  # Japanese
    "jv-ID",  # Javanese
    "kea-CV",  # Kabuverdianu
    "kn-IN",  # Kannada
    "kk-KZ",  # Kazakh
    "km-KH",  # Khmer
    "ko-KR",  # Korean
    "ku-TR",  # Kurdish
    "ky-KG",  # Kyrgyz
    "lo-LA",  # Lao
    "lv-LV",  # Latvian
    "ln-CD",  # Lingala
    "lt-LT",  # Lithuanian
    "luo-KE",  # Luo
    "lb-LU",  # Luxembourgish
    "mk-MK",  # Macedonian
    "ms-MY",  # Malay
    "ml-IN",  # Malayalam
    "mt-MT",  # Maltese
    "zh-CN",  # Mandarin Chinese
    "mi-NZ",  # Māori
    "mr-IN",  # Marathi
    "mn-MN",  # Mongolian
    "ne-NP",  # Nepali
    "nso-ZA",  # Northern Sotho
    "no-NO",  # Norwegian
    "oc-FR",  # Occitan
    "or-IN",  # Odia
    "ps-AF",  # Pashto
    "fa-IR",  # Persian
    "pl-PL",  # Polish
    "pt-PT",  # Portuguese
    "pa-IN",  # Punjabi
    "ro-RO",  # Romanian
    "ru-RU",  # Russian
    "sr-RS",  # Serbian
    "sn-ZW",  # Shona
    "sd-PK",  # Sindhi
    "sk-SK",  # Slovak
    "sl-SI",  # Slovenian
    "so-SO",  # Somali
    "es-ES",  # Spanish
    "sw-KE",  # Swahili
    "sv-SE",  # Swedish
    "ta-IN",  # Tamil
    "tg-TJ",  # Tajik
    "te-IN",  # Telugu
    "th-TH",  # Thai
    "tr-TR",  # Turkish
    "uk-UA",  # Ukrainian
    "umb-AO",  # Umbundu
    "ur-PK",  # Urdu
    "uz-UZ",  # Uzbek
    "vi-VN",  # Vietnamese
    "cy-GB",  # Welsh
    "wo-SN",  # Wolof
    "xh-ZA",  # Xhosa
    "zu-ZA",  # Zulu
]

STT_MODELS = {
    "scribe_v1": "Scribe v1",
    "scribe_v1_experimental": "Scribe v1 Experimental",
    "scribe_v2": "Scribe v2 Realtime",
}
