"""Constants for the OpenRouter integration."""

from __future__ import annotations

import logging

from homeassistant.const import CONF_LLM_HASS_API, CONF_PROMPT
from homeassistant.helpers import llm

DOMAIN = "open_router"
LOGGER = logging.getLogger(__package__)

CONF_CHAT_MODEL = "chat_model"
CONF_PROVIDER = "provider"
CONF_WEB_SEARCH = "web_search"

SECTION_OPTIONS = "section_options"
SECTION_MODEL = "section_model"

DEFAULT_CONVERSATION_NAME = "OpenRouter Agent"

RECOMMENDED_WEB_SEARCH = False

SUPPORTED_PARAMETER_STRUCTURED_OUTPUTS = "structured_outputs"
SUPPORTED_PARAMETER_TOOLS = "tools"

RECOMMENDED_CONVERSATION_OPTIONS = {
    CONF_LLM_HASS_API: [llm.LLM_API_ASSIST],
    CONF_PROMPT: llm.DEFAULT_INSTRUCTIONS_PROMPT,
    CONF_WEB_SEARCH: RECOMMENDED_WEB_SEARCH,
}
