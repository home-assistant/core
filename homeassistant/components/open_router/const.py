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
CONF_OUTPUT_MODALITIES = "output_modalities"

RECOMMENDED_TTS_SPEED = 1.0
RECOMMENDED_TTS_VOICE = "alloy"
RECOMMENDED_WEB_SEARCH = "off"

# OpenAI-compatible voices offered when a model does not expose its own voices
FALLBACK_TTS_VOICES = (
    "alloy",
    "ash",
    "ballad",
    "coral",
    "echo",
    "fable",
    "nova",
    "onyx",
    "sage",
    "shimmer",
    "verse",
    "marin",
    "cedar",
)

RECOMMENDED_CONVERSATION_OPTIONS = {
    CONF_RECOMMENDED: True,
    CONF_LLM_HASS_API: [llm.LLM_API_ASSIST],
    CONF_PROMPT: llm.DEFAULT_INSTRUCTIONS_PROMPT,
    CONF_WEB_SEARCH: RECOMMENDED_WEB_SEARCH,
}
