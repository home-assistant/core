"""Constants for the LM Studio integration."""

from __future__ import annotations

DOMAIN = "lmstudio"

# Default configuration
DEFAULT_BASE_URL = "http://localhost:1234/v1"
DEFAULT_API_KEY = "lm-studio"
DEFAULT_MODEL = "mistralai/mistral-small-3.2"
DEFAULT_TIMEOUT = 10
DEFAULT_MAX_TOKENS = 150
DEFAULT_TEMPERATURE = 0.7
DEFAULT_TOP_P = 1.0
DEFAULT_CONVERSATION_NAME = "LM Studio"
DEFAULT_AI_TASK_NAME = "LM Studio AI"

# Configuration keys
CONF_BASE_URL = "base_url"
CONF_API_KEY = "api_key"
CONF_MODEL = "model"
CONF_MAX_TOKENS = "max_tokens"
CONF_TEMPERATURE = "temperature"
CONF_TOP_P = "top_p"
CONF_PROMPT = "prompt"
CONF_STREAM = "stream"

# Recommended options for subentries
RECOMMENDED_CONVERSATION_OPTIONS = {
    CONF_MAX_TOKENS: DEFAULT_MAX_TOKENS,
    CONF_TEMPERATURE: DEFAULT_TEMPERATURE,
    CONF_TOP_P: DEFAULT_TOP_P,
}

RECOMMENDED_AI_TASK_OPTIONS = {
    CONF_MAX_TOKENS: 500,
    CONF_TEMPERATURE: 0.3,
    CONF_TOP_P: 0.95,
}
