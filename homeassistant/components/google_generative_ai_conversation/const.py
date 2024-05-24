"""Constants for the Google Generative AI Conversation integration."""

import logging

DOMAIN = "google_generative_ai_conversation"
LOGGER = logging.getLogger(__package__)
CONF_PROMPT = "prompt"
DEFAULT_PROMPT = "Answer in plain text. Keep it simple and to the point."

CONF_RECOMMENDED = "recommended"
CONF_CHAT_MODEL = "chat_model"
RECOMMENDED_CHAT_MODEL = "models/gemini-1.5-flash-latest"
CONF_TEMPERATURE = "temperature"
RECOMMENDED_TEMPERATURE = 1.0
CONF_TOP_P = "top_p"
RECOMMENDED_TOP_P = 0.95
CONF_TOP_K = "top_k"
RECOMMENDED_TOP_K = 64
CONF_MAX_TOKENS = "max_tokens"
RECOMMENDED_MAX_TOKENS = 150
