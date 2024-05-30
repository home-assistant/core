"""Constants for the OpenAI Conversation integration."""

import logging

DOMAIN = "azure_openai_conversation"
LOGGER = logging.getLogger(__package__)

CONF_AZURE_OPENAI_RESOURCE = "azure_openai_resource"
CONF_RECOMMENDED = "recommended"
CONF_PROMPT = "prompt"
CONF_CHAT_MODEL = "chat_model"
RECOMMENDED_CHAT_MODEL = "gpt-4"
CONF_MAX_TOKENS = "max_tokens"
RECOMMENDED_MAX_TOKENS = 150
CONF_TOP_P = "top_p"
RECOMMENDED_TOP_P = 1.0
CONF_TEMPERATURE = "temperature"
RECOMMENDED_TEMPERATURE = 1.0
AZURE_OPEN_API_VERSION = "2024-02-01"
