"""Constants for the Mistral AI integration."""

import logging

from homeassistant.const import CONF_LLM_HASS_API, CONF_PROMPT
from homeassistant.helpers import llm

DOMAIN = "mistral_ai"
LOGGER: logging.Logger = logging.getLogger(__package__)

DEFAULT_NAME = "Mistral"
DEFAULT_CONVERSATION_NAME = "Mistral conversation"
DEFAULT_STT_NAME = "Mistral STT"
DEFAULT_TTS_NAME = "Mistral TTS"

CONF_CHAT_MODEL = "chat_model"
CONF_MAX_TOKENS = "max_tokens"
CONF_TEMPERATURE = "temperature"
CONF_TOP_P = "top_p"
CONF_RECOMMENDED = "recommended"

RECOMMENDED_CHAT_MODEL = "mistral-small-latest"
RECOMMENDED_MAX_TOKENS = 3000
RECOMMENDED_TEMPERATURE = 0.7
RECOMMENDED_TOP_P = 1.0

# Modèles audio Mistral
RECOMMENDED_STT_MODEL = "voxtral-mini-latest"
RECOMMENDED_TTS_MODEL = "voxtral-mini-tts-latest"

# Modèles de secours proposés si l'appel /v1/models échoue (saisie libre possible)
MISTRAL_MODELS = [
    "mistral-small-latest",
    "mistral-medium-latest",
    "mistral-large-latest",
    "ministral-3b-latest",
    "ministral-8b-latest",
    "open-mistral-nemo",
]

STT_MODELS = [
    "voxtral-mini-latest",
    "voxtral-mini-2602",
]

TTS_MODELS = [
    "voxtral-mini-tts-latest",
    "voxtral-mini-tts-2603",
]

DEFAULT = {
    CONF_CHAT_MODEL: RECOMMENDED_CHAT_MODEL,
    CONF_MAX_TOKENS: RECOMMENDED_MAX_TOKENS,
    CONF_TEMPERATURE: RECOMMENDED_TEMPERATURE,
    CONF_TOP_P: RECOMMENDED_TOP_P,
}

RECOMMENDED_CONVERSATION_OPTIONS = {
    CONF_RECOMMENDED: True,
    CONF_LLM_HASS_API: [llm.LLM_API_ASSIST],
    CONF_PROMPT: llm.DEFAULT_INSTRUCTIONS_PROMPT,
}

RECOMMENDED_STT_OPTIONS = {
    CONF_CHAT_MODEL: RECOMMENDED_STT_MODEL,
}

RECOMMENDED_TTS_OPTIONS = {
    CONF_CHAT_MODEL: RECOMMENDED_TTS_MODEL,
}

DEFAULT_MODEL_BY_TYPE = {
    "conversation": RECOMMENDED_CHAT_MODEL,
    "stt": RECOMMENDED_STT_MODEL,
    "tts": RECOMMENDED_TTS_MODEL,
}
