"""Constants for the OpenAI Conversation integration."""

import logging

DOMAIN = "openai_conversation"
LOGGER = logging.getLogger(__package__)

CONF_RECOMMENDED = "recommended"
CONF_PROMPT = "prompt"
CONF_CHAT_MODEL = "chat_model"
RECOMMENDED_CHAT_MODEL = "gpt-4o-mini"
CONF_MAX_TOKENS = "max_tokens"
RECOMMENDED_MAX_TOKENS = 150
CONF_TOP_P = "top_p"
RECOMMENDED_TOP_P = 1.0
CONF_TEMPERATURE = "temperature"
RECOMMENDED_TEMPERATURE = 1.0
CONF_REASONING_EFFORT = "reasoning_effort"
RECOMMENDED_REASONING_EFFORT = "low"

UNSUPPORTED_MODELS = [
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
