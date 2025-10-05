"""Constants for the Anthropic integration."""

import logging

DOMAIN = "anthropic"
LOGGER = logging.getLogger(__package__)

DEFAULT_CONVERSATION_NAME = "Claude conversation"

CONF_RECOMMENDED = "recommended"
CONF_PROMPT = "prompt"
CONF_CHAT_MODEL = "chat_model"
RECOMMENDED_CHAT_MODEL = "claude-3-5-haiku-latest"
CONF_MAX_TOKENS = "max_tokens"
RECOMMENDED_MAX_TOKENS = 3000
CONF_TEMPERATURE = "temperature"
RECOMMENDED_TEMPERATURE = 1.0
CONF_THINKING_BUDGET = "thinking_budget"
RECOMMENDED_THINKING_BUDGET = 0
MIN_THINKING_BUDGET = 1024
CONF_WEB_SEARCH = "web_search"
RECOMMENDED_WEB_SEARCH = False
CONF_WEB_SEARCH_USER_LOCATION = "user_location"
RECOMMENDED_WEB_SEARCH_USER_LOCATION = False
CONF_WEB_SEARCH_MAX_USES = "web_search_max_uses"
RECOMMENDED_WEB_SEARCH_MAX_USES = 5
CONF_WEB_SEARCH_CITY = "city"
CONF_WEB_SEARCH_REGION = "region"
CONF_WEB_SEARCH_COUNTRY = "country"
CONF_WEB_SEARCH_TIMEZONE = "timezone"

NON_THINKING_MODELS = [
    "claude-3-5",  # Both sonnet and haiku
    "claude-3-opus",
    "claude-3-haiku",
]

WEB_SEARCH_UNSUPPORTED_MODELS = [
    "claude-3-haiku",
    "claude-3-opus",
    "claude-3-5-sonnet-20240620",
    "claude-3-5-sonnet-20241022",
]
