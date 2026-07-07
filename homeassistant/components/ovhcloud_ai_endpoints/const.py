"""Constants for the OVHcloud AI Endpoints integration."""

import logging

from homeassistant.const import CONF_LLM_HASS_API, CONF_PROMPT
from homeassistant.helpers import llm

DOMAIN = "ovhcloud_ai_endpoints"
LOGGER = logging.getLogger(__package__)

BASE_URL = "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1"

RECOMMENDED_CONVERSATION_OPTIONS = {
    CONF_LLM_HASS_API: [llm.LLM_API_ASSIST],
    CONF_PROMPT: llm.DEFAULT_INSTRUCTIONS_PROMPT,
}
