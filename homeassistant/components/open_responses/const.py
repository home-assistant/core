"""Constants for the Open Responses integration."""

import logging

from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.helpers import llm

DOMAIN = "open_responses"
LOGGER: logging.Logger = logging.getLogger(__package__)

DEFAULT_CONVERSATION_NAME = "Open Responses Conversation"
DEFAULT_NAME = "Open Responses"

CONF_BASE_URL = "base_url"
CONF_GENERATED_DEFAULT_SUBENTRY = "generated_default_subentry"
CONF_MAX_OUTPUT_TOKENS = "max_output_tokens"
CONF_PROMPT = "prompt"
CONF_STORE_RESPONSES = "store_responses"

RECOMMENDED_MAX_OUTPUT_TOKENS = 3000
RECOMMENDED_STORE_RESPONSES = False

RECOMMENDED_CONVERSATION_OPTIONS = {
    CONF_LLM_HASS_API: [llm.LLM_API_ASSIST],
    CONF_PROMPT: llm.DEFAULT_INSTRUCTIONS_PROMPT,
    CONF_MAX_OUTPUT_TOKENS: RECOMMENDED_MAX_OUTPUT_TOKENS,
    CONF_STORE_RESPONSES: RECOMMENDED_STORE_RESPONSES,
}
