"""Constants for the Google Generative AI Conversation integration."""

import logging

from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.helpers import llm

LOGGER = logging.getLogger(__package__)

DOMAIN = "google_generative_ai_conversation"
DEFAULT_TITLE = "Google Generative AI"

DEFAULT_CONVERSATION_NAME = "Google AI Conversation"
DEFAULT_STT_NAME = "Google AI STT"
DEFAULT_TTS_NAME = "Google AI TTS"
DEFAULT_AI_TASK_NAME = "Google AI Task"

CONF_PROMPT = "prompt"
DEFAULT_STT_PROMPT = "Transcribe the attached audio"

CONF_RECOMMENDED = "recommended"
CONF_CHAT_MODEL = "chat_model"
RECOMMENDED_CHAT_MODEL = "models/gemini-2.5-flash"
RECOMMENDED_STT_MODEL = RECOMMENDED_CHAT_MODEL
RECOMMENDED_TTS_MODEL = "models/gemini-2.5-flash-preview-tts"
RECOMMENDED_IMAGE_MODEL = "models/gemini-2.5-flash-image"
CONF_TEMPERATURE = "temperature"
RECOMMENDED_TEMPERATURE = 1.0
CONF_TOP_P = "top_p"
RECOMMENDED_TOP_P = 0.95
CONF_TOP_K = "top_k"
RECOMMENDED_TOP_K = 64
CONF_MAX_TOKENS = "max_tokens"
RECOMMENDED_MAX_TOKENS = 3000
# Input 5000, output 19400 = 0.05 USD
RECOMMENDED_AI_TASK_MAX_TOKENS = 19400
CONF_HARASSMENT_BLOCK_THRESHOLD = "harassment_block_threshold"
CONF_HATE_BLOCK_THRESHOLD = "hate_block_threshold"
CONF_SEXUAL_BLOCK_THRESHOLD = "sexual_block_threshold"
CONF_DANGEROUS_BLOCK_THRESHOLD = "dangerous_block_threshold"
RECOMMENDED_HARM_BLOCK_THRESHOLD = "BLOCK_MEDIUM_AND_ABOVE"
CONF_USE_GOOGLE_SEARCH_TOOL = "enable_google_search_tool"
RECOMMENDED_USE_GOOGLE_SEARCH_TOOL = False

TIMEOUT_MILLIS = 10000
FILE_POLLING_INTERVAL_SECONDS = 0.05

RECOMMENDED_CONVERSATION_OPTIONS = {
    CONF_PROMPT: llm.DEFAULT_INSTRUCTIONS_PROMPT,
    CONF_LLM_HASS_API: [llm.LLM_API_ASSIST],
    CONF_RECOMMENDED: True,
}

RECOMMENDED_STT_OPTIONS = {
    CONF_PROMPT: DEFAULT_STT_PROMPT,
    CONF_RECOMMENDED: True,
}

RECOMMENDED_TTS_OPTIONS = {
    CONF_RECOMMENDED: True,
}

RECOMMENDED_AI_TASK_OPTIONS = {
    CONF_RECOMMENDED: True,
}
