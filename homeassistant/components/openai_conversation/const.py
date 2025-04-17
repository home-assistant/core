"""Constants for the OpenAI Conversation integration."""

import logging

DOMAIN = "openai_conversation"
LOGGER: logging.Logger = logging.getLogger(__package__)

CONF_CHAT_MODEL = "chat_model"
CONF_FILENAMES = "filenames"
CONF_MAX_TOKENS = "max_tokens"
CONF_PROMPT = "prompt"
CONF_PROMPT = "prompt"
CONF_REASONING_EFFORT = "reasoning_effort"
CONF_RECOMMENDED = "recommended"
CONF_TEMPERATURE = "temperature"
CONF_TOP_P = "top_p"
CONF_WEB_SEARCH = "web_search"
CONF_WEB_SEARCH_USER_LOCATION = "user_location"
CONF_WEB_SEARCH_CONTEXT_SIZE = "search_context_size"
CONF_WEB_SEARCH_CITY = "city"
CONF_WEB_SEARCH_REGION = "region"
CONF_WEB_SEARCH_COUNTRY = "country"
CONF_WEB_SEARCH_TIMEZONE = "timezone"
RECOMMENDED_CHAT_MODEL = "gpt-4o-mini"
RECOMMENDED_MAX_TOKENS = 150
RECOMMENDED_REASONING_EFFORT = "low"
RECOMMENDED_TEMPERATURE = 1.0
RECOMMENDED_TOP_P = 1.0
RECOMMENDED_WEB_SEARCH = False
RECOMMENDED_WEB_SEARCH_CONTEXT_SIZE = "medium"
RECOMMENDED_WEB_SEARCH_USER_LOCATION = False

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

WEB_SEARCH_MODELS: list[str] = [
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4o",
    "gpt-4o-search-preview",
    "gpt-4o-mini",
    "gpt-4o-mini-search-preview",
]
