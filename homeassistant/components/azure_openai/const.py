"""Constants for the Azure OpenAI integration."""

import logging
from typing import Any

from homeassistant.const import CONF_LLM_HASS_API, CONF_PROMPT
from homeassistant.helpers import llm

DOMAIN = "azure_openai"
LOGGER: logging.Logger = logging.getLogger(__package__)

DEFAULT_CONVERSATION_NAME = "Azure OpenAI Conversation"
DEFAULT_AI_TASK_NAME = "Azure OpenAI AI Task"
DEFAULT_STT_NAME = "Azure OpenAI STT"
DEFAULT_TTS_NAME = "Azure OpenAI TTS"

CONF_BASE_URL = "base_url"
CONF_CHAT_MODEL = "chat_model"
CONF_MODEL_FAMILY = "model_family"
CONF_IMAGE_MODEL = "image_model"
CONF_IMAGE_DEPLOYMENT = "image_deployment"
CONF_CODE_INTERPRETER = "code_interpreter"
CONF_MAX_TOKENS = "max_tokens"
CONF_PRO_MODE = "pro_mode"
CONF_REASONING_EFFORT = "reasoning_effort"
CONF_REASONING_SUMMARY = "reasoning_summary"
CONF_RECOMMENDED = "recommended"
CONF_STT_MODEL = "stt_model"
CONF_TEMPERATURE = "temperature"
CONF_TOP_P = "top_p"
CONF_TTS_MODEL = "tts_model"
CONF_TTS_SPEED = "tts_speed"
CONF_VERBOSITY = "verbosity"
CONF_WEB_SEARCH = "web_search"
CONF_WEB_SEARCH_USER_LOCATION = "user_location"
CONF_WEB_SEARCH_CONTEXT_SIZE = "search_context_size"
CONF_WEB_SEARCH_CITY = "city"
CONF_WEB_SEARCH_REGION = "region"
CONF_WEB_SEARCH_COUNTRY = "country"
CONF_WEB_SEARCH_TIMEZONE = "timezone"
CONF_WEB_SEARCH_INLINE_CITATIONS = "inline_citations"
RECOMMENDED_CODE_INTERPRETER = False
RECOMMENDED_MAX_TOKENS = 3000
RECOMMENDED_PRO_MODE = False
RECOMMENDED_REASONING_EFFORT = "low"
RECOMMENDED_REASONING_SUMMARY = "auto"
RECOMMENDED_TEMPERATURE = 1.0
RECOMMENDED_TOP_P = 1.0
RECOMMENDED_TTS_SPEED = 1.0
RECOMMENDED_VERBOSITY = "medium"
RECOMMENDED_WEB_SEARCH = False
RECOMMENDED_WEB_SEARCH_CONTEXT_SIZE = "medium"
RECOMMENDED_WEB_SEARCH_USER_LOCATION = False
RECOMMENDED_WEB_SEARCH_INLINE_CITATIONS = False
DEFAULT_STT_PROMPT = (
    "The following conversation is a smart home user talking to Home Assistant."
)

RECOMMENDED_CONVERSATION_OPTIONS = {
    CONF_RECOMMENDED: True,
    CONF_LLM_HASS_API: [llm.LLM_API_ASSIST],
    CONF_PROMPT: llm.DEFAULT_INSTRUCTIONS_PROMPT,
}
RECOMMENDED_AI_TASK_OPTIONS = {
    CONF_RECOMMENDED: True,
}
RECOMMENDED_STT_OPTIONS: dict[str, Any] = {}
RECOMMENDED_TTS_OPTIONS = {
    CONF_PROMPT: "",
}
