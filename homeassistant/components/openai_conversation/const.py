"""Constants for the OpenAI Conversation integration."""

import logging
from typing import Any

from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.helpers import llm

DOMAIN = "openai_conversation"
LOGGER: logging.Logger = logging.getLogger(__package__)

DEFAULT_CONVERSATION_NAME = "OpenAI Conversation"
DEFAULT_AI_TASK_NAME = "OpenAI AI Task"
DEFAULT_STT_NAME = "OpenAI STT"
DEFAULT_TTS_NAME = "OpenAI TTS"
DEFAULT_NAME = "OpenAI Conversation"

CONF_CHAT_MODEL = "chat_model"
CONF_IMAGE_MODEL = "image_model"
CONF_CODE_INTERPRETER = "code_interpreter"
CONF_FILENAMES = "filenames"
CONF_MAX_TOKENS = "max_tokens"
CONF_PROMPT = "prompt"
CONF_REASONING_EFFORT = "reasoning_effort"
CONF_REASONING_SUMMARY = "reasoning_summary"
CONF_RECOMMENDED = "recommended"
CONF_TEMPERATURE = "temperature"
CONF_TOP_P = "top_p"
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
RECOMMENDED_CHAT_MODEL = "gpt-4o-mini"
RECOMMENDED_IMAGE_MODEL = "gpt-image-1.5"
RECOMMENDED_MAX_TOKENS = 3000
RECOMMENDED_REASONING_EFFORT = "low"
RECOMMENDED_REASONING_SUMMARY = "auto"
RECOMMENDED_STT_MODEL = "gpt-4o-mini-transcribe"
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

UNSUPPORTED_MODELS: list[str] = [
    "o1-mini",
    "o1-mini-2024-09-12",
    "o1-preview",
    "o1-preview-2024-09-12",
    "gpt-4o-realtime-preview",
    "gpt-4o-realtime-preview-2024-12-17",
    "gpt-4o-realtime-preview-2024-10-01",
    "gpt-4o-mini-realtime-preview",
    "gpt-4o-mini-realtime-preview-2024-12-17",
]

UNSUPPORTED_WEB_SEARCH_MODELS: list[str] = [
    "gpt-5-nano",
    "gpt-3.5",
    "gpt-4-turbo",
    "gpt-4.1-nano",
    "o1",
    "o3-mini",
]

UNSUPPORTED_IMAGE_MODELS: list[str] = [
    "gpt-5-mini",
    "o3-mini",
    "o4",
    "o1",
    "gpt-3.5",
    "gpt-4-turbo",
]

UNSUPPORTED_CODE_INTERPRETER_MODELS: list[str] = [
    "gpt-5-pro",
    "gpt-5.2-pro",
    "gpt-5-codex",
    "gpt-5.1-codex",
    "gpt-5.2-codex",
]

UNSUPPORTED_EXTENDED_CACHE_RETENTION_MODELS: list[str] = [
    "o1",
    "o3",
    "o4",
    "gpt-3.5",
    "gpt-4-turbo",
    "gpt-4o",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
    "gpt-5-mini",
    "gpt-5-nano",
]

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
    CONF_CHAT_MODEL: "gpt-4o-mini-tts",
}
