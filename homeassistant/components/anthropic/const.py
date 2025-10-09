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

NON_THINKING_MODELS = [
    "claude-3-5",  # Both sonnet and haiku
    "claude-3-opus",
    "claude-3-haiku",
]
