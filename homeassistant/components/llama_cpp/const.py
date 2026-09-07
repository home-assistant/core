"""Constants for the llama.cpp integration."""

import logging

DOMAIN = "llama_cpp"
LOGGER = logging.getLogger(__package__)

DEFAULT_CONVERSATION_NAME = "llama.cpp Conversation"

CONF_CHAT_MODEL = "chat_model"
CONF_MAX_TOKENS = "max_tokens"
CONF_TEMPERATURE = "temperature"
CONF_TOP_P = "top_p"
CONF_BASE_URL = "base_url"
CONF_RECOMMENDED = "recommended"
CONF_STREAMING = "streaming"

# Some servers set placeholder model names which we can use as a default
DEFAULT_MODEL = "gpt-3.5-turbo"
RECOMMENDED_CHAT_MODELS = [
    DEFAULT_MODEL,
    "gpt-4",
    "local-model",
]
RECOMMENDED_MAX_TOKENS = 3000
RECOMMENDED_TEMPERATURE = 0.7
RECOMMENDED_TOP_P = 1.0

DEFAULT_BASE_URL = "http://localhost:8080/v1"
DEFAULT_API_KEY = "sk-0000000000000000000"
