"""Constants for the OpenRouter integration."""

import logging

from homeassistant.const import CONF_LLM_HASS_API, CONF_PROMPT
from homeassistant.helpers import llm

DOMAIN = "open_router"
LOGGER = logging.getLogger(__package__)

CONF_RECOMMENDED = "recommended"
CONF_TTS_SPEED = "tts_speed"
CONF_TTS_VOICE = "tts_voice"
CONF_WEB_SEARCH = "web_search"

RECOMMENDED_TTS_MODEL = "openai/gpt-4o-mini-tts-2025-12-15"
RECOMMENDED_TTS_SPEED = 1.0
RECOMMENDED_TTS_VOICE = "alloy"
RECOMMENDED_STT_MODEL = "openai/whisper-large-v3"
RECOMMENDED_WEB_SEARCH = False

DEFAULT_STT_NAME = "OpenRouter STT"
DEFAULT_TTS_NAME = "OpenRouter TTS"

RECOMMENDED_CONVERSATION_OPTIONS = {
    CONF_RECOMMENDED: True,
    CONF_LLM_HASS_API: [llm.LLM_API_ASSIST],
    CONF_PROMPT: llm.DEFAULT_INSTRUCTIONS_PROMPT,
    CONF_WEB_SEARCH: RECOMMENDED_WEB_SEARCH,
}
