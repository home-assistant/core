"""Constants for the Anthropic integration."""

import logging

DOMAIN = "anthropic"
LOGGER = logging.getLogger(__package__)

CONF_RECOMMENDED = "recommended"
CONF_PROMPT = "prompt"
CONF_CHAT_MODEL = "chat_model"
RECOMMENDED_CHAT_MODEL = "claude-3-haiku-20240307"
CONF_MAX_TOKENS = "max_tokens"
RECOMMENDED_MAX_TOKENS = 1024
CONF_TEMPERATURE = "temperature"
RECOMMENDED_TEMPERATURE = 1.0
CONF_THINKING_BUDGET = "thinking_budget"
RECOMMENDED_THINKING_BUDGET = 0
MIN_THINKING_BUDGET = 1024

THINKING_MODELS = ["claude-3-7-sonnet-20250219", "claude-3-7-sonnet-latest"]
