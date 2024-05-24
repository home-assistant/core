"""Constants for the OpenAI Conversation integration."""

import logging

DOMAIN = "openai_conversation"
LOGGER = logging.getLogger(__package__)
CONF_PROMPT = "prompt"
DEFAULT_PROMPT = """Answer in plain text. Keep it simple and to the point."""
CONF_CHAT_MODEL = "chat_model"
DEFAULT_CHAT_MODEL = "gpt-3.5-turbo"
CONF_MAX_TOKENS = "max_tokens"
DEFAULT_MAX_TOKENS = 150
CONF_TOP_P = "top_p"
DEFAULT_TOP_P = 1
CONF_TEMPERATURE = "temperature"
DEFAULT_TEMPERATURE = 0.5
