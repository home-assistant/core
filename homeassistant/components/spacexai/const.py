"""Constants for the SpaceXAI integration."""

from logging import Logger, getLogger

from homeassistant.const import CONF_LLM_HASS_API, CONF_PROMPT
from homeassistant.helpers import llm

DOMAIN = "spacexai"
LOGGER: Logger = getLogger(__package__)

DEFAULT_CONVERSATION_NAME = "Grok"
MAX_TOOL_ITERATIONS = 10

RECOMMENDED_CONVERSATION_OPTIONS = {
    CONF_LLM_HASS_API: [llm.LLM_API_ASSIST],
    CONF_PROMPT: llm.DEFAULT_INSTRUCTIONS_PROMPT,
}
