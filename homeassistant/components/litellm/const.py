"""Constants for the LiteLLM integration."""

import logging

from homeassistant.const import CONF_LLM_HASS_API, CONF_PROMPT
from homeassistant.helpers import llm

DOMAIN = "litellm"
LOGGER = logging.getLogger(__package__)

# LiteLLM proxies may run without authentication. The OpenAI client requires a
# non-empty API key, so we send a placeholder when the user did not provide one.
PLACEHOLDER_API_KEY = "sk-no-key-required"

RECOMMENDED_CONVERSATION_OPTIONS = {
    CONF_LLM_HASS_API: [llm.LLM_API_ASSIST],
    CONF_PROMPT: llm.DEFAULT_INSTRUCTIONS_PROMPT,
}
