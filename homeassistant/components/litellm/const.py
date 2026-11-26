"""Constants for the LiteLLM integration."""

import logging

from homeassistant.const import CONF_LLM_HASS_API, CONF_PROMPT
from homeassistant.helpers import llm

DOMAIN = "litellm"
LOGGER = logging.getLogger(__package__)
CONF_STT_CUSTOM_PROMPT_KEYWORDS = "custom_prompt_keywords"
CONF_STT_KEYWORDS = "keywords"
CONF_STT_PROMPT = "prompt"
CONF_TTS_VOICE = "voice"

# LiteLLM proxies may run without authentication. The OpenAI client requires a
# non-empty API key, so we send a placeholder when the user did not provide one.
PLACEHOLDER_API_KEY = "sk-no-key-required"

RECOMMENDED_CONVERSATION_OPTIONS = {
    CONF_LLM_HASS_API: [llm.LLM_API_ASSIST],
    CONF_PROMPT: llm.DEFAULT_INSTRUCTIONS_PROMPT,
}

# LiteLLM does not report the languages of a backend model, so this is the
# OpenAI speech model list and the selected backend may reject a language.
SUPPORTED_LANGUAGES = [
    "af-ZA",  # Afrikaans
    "ar-SA",  # Arabic
    "hy-AM",  # Armenian
    "az-AZ",  # Azerbaijani
    "be-BY",  # Belarusian
    "bs-BA",  # Bosnian
    "bg-BG",  # Bulgarian
    "ca-ES",  # Catalan
    "zh-CN",  # Chinese (Mandarin)
    "hr-HR",  # Croatian
    "cs-CZ",  # Czech
    "da-DK",  # Danish
    "nl-NL",  # Dutch
    "en-US",  # English
    "et-EE",  # Estonian
    "fi-FI",  # Finnish
    "fr-FR",  # French
    "gl-ES",  # Galician
    "de-DE",  # German
    "el-GR",  # Greek
    "he-IL",  # Hebrew
    "hi-IN",  # Hindi
    "hu-HU",  # Hungarian
    "is-IS",  # Icelandic
    "id-ID",  # Indonesian
    "it-IT",  # Italian
    "ja-JP",  # Japanese
    "kn-IN",  # Kannada
    "kk-KZ",  # Kazakh
    "ko-KR",  # Korean
    "lv-LV",  # Latvian
    "lt-LT",  # Lithuanian
    "mk-MK",  # Macedonian
    "ms-MY",  # Malay
    "mr-IN",  # Marathi
    "mi-NZ",  # Maori
    "ne-NP",  # Nepali
    "no-NO",  # Norwegian
    "fa-IR",  # Persian
    "pl-PL",  # Polish
    "pt-PT",  # Portuguese
    "ro-RO",  # Romanian
    "ru-RU",  # Russian
    "sr-RS",  # Serbian
    "sk-SK",  # Slovak
    "sl-SI",  # Slovenian
    "es-ES",  # Spanish
    "sw-KE",  # Swahili
    "sv-SE",  # Swedish
    "fil-PH",  # Tagalog (Filipino)
    "ta-IN",  # Tamil
    "th-TH",  # Thai
    "tr-TR",  # Turkish
    "uk-UA",  # Ukrainian
    "ur-PK",  # Urdu
    "vi-VN",  # Vietnamese
    "cy-GB",  # Welsh
]
