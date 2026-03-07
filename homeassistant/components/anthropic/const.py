"""Constants for the Anthropic integration."""

import logging

DOMAIN = "anthropic"
LOGGER = logging.getLogger(__package__)

DEFAULT_CONVERSATION_NAME = "Claude conversation"
DEFAULT_AI_TASK_NAME = "Claude AI Task"

CONF_RECOMMENDED = "recommended"
CONF_PROMPT = "prompt"
CONF_CHAT_MODEL = "chat_model"
CONF_CODE_EXECUTION = "code_execution"
CONF_MAX_TOKENS = "max_tokens"
CONF_TEMPERATURE = "temperature"
CONF_THINKING_BUDGET = "thinking_budget"
CONF_THINKING_EFFORT = "thinking_effort"
CONF_WEB_SEARCH = "web_search"
CONF_WEB_SEARCH_USER_LOCATION = "user_location"
CONF_WEB_SEARCH_MAX_USES = "web_search_max_uses"
CONF_WEB_SEARCH_CITY = "city"
CONF_WEB_SEARCH_REGION = "region"
CONF_WEB_SEARCH_COUNTRY = "country"
CONF_WEB_SEARCH_TIMEZONE = "timezone"

DEFAULT = {
    CONF_CHAT_MODEL: "claude-haiku-4-5",
    CONF_CODE_EXECUTION: False,
    CONF_MAX_TOKENS: 3000,
    CONF_TEMPERATURE: 1.0,
    CONF_THINKING_BUDGET: 0,
    CONF_THINKING_EFFORT: "low",
    CONF_WEB_SEARCH: False,
    CONF_WEB_SEARCH_USER_LOCATION: False,
    CONF_WEB_SEARCH_MAX_USES: 5,
}

MIN_THINKING_BUDGET = 1024

NON_THINKING_MODELS = [
    "claude-3-haiku",
]

NON_ADAPTIVE_THINKING_MODELS = [
    "claude-opus-4-5",
    "claude-sonnet-4-5",
    "claude-haiku-4-5",
    "claude-opus-4-1",
    "claude-opus-4-0",
    "claude-opus-4-20250514",
    "claude-sonnet-4-0",
    "claude-sonnet-4-20250514",
    "claude-3-haiku",
]

UNSUPPORTED_STRUCTURED_OUTPUT_MODELS = [
    "claude-opus-4-1",
    "claude-opus-4-0",
    "claude-opus-4-20250514",
    "claude-sonnet-4-0",
    "claude-sonnet-4-20250514",
    "claude-3-haiku",
]

WEB_SEARCH_UNSUPPORTED_MODELS = [
    "claude-3-haiku",
]

CODE_EXECUTION_UNSUPPORTED_MODELS = [
    "claude-3-haiku",
]

DEPRECATED_MODELS = [
    "claude-3",
]
